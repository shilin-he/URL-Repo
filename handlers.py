import os
import re
import cgi
import urllib
import urlparse
import logging
import time
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import login_required
from google.appengine.ext.webapp import template
from models import *
import helper


logging.getLogger().setLevel(logging.DEBUG)


class BaseHandler(webapp.RequestHandler):
    def render(self, template_name, context):
        template_path = os.path.join(
            os.path.dirname(__file__), "templates", template_name + ".html")

        context['user'] = users.get_current_user()
        context["login_url"] = users.create_login_url('/my_bookmarks')
        context["logout_url"] = users.create_logout_url('/') 
            
        self.response.out.write(
            template.render(template_path, context))


class MainHandler(BaseHandler):
    def get(self):
        context = {}
        self.render("main", context)


class ImportHandler(BaseHandler):
    @login_required
    def get(self):
        context = {
            "err_msg": None,
        }
        self.render("import_export", context)

    def post(self):
        data = self.request.get("datafile")
        err_msg = []
        if not data:
            err_msg.append("Data file is required.")
        else:
            file_name = self.request.POST["datafile"].filename
            file_ext = os.path.splitext(file_name)[1]
            if file_ext == ".json":
                data = re.sub(r',]', ']', data)
                try:
                    data = json.loads(data, encoding='utf-8')
                    helper.save_bookmarks(data, None)
                except ValueError:
                    err_msg.append("Invalid data file.")
            elif file_ext in [".htm", ".html"]:
                try:
                    data = data.decode('utf-8')
                    parser = helper.NetscapeBookmarkParser()
                    parser.feed(data)
                except Exception, e:
                    err_msg.append(str(e.args))
            else:
                err_msg.append("Wrong file type.")
        if err_msg:
            context = {
                "err_msg": err_msg,
            }
            self.render("import_export", context)
        else:
            memcache.delete('nav')
            self.redirect('/my_bookmarks')


class ExportJSONHandler(webapp.RequestHandler):
    @login_required
    def get(self):
        output = helper.export_to_firefox_json_format() 
        self.response.headers.add_header('content-disposition',
                'attachment', filename='bookmarks.json')
        self.response.out.write(str(output))
        

class ExportHTMLHandler(webapp.RequestHandler):
    @login_required
    def get(self):
        output = helper.export_to_netscape_format()
        self.response.headers.add_header('content-disposition',
                'attachment', filename='bookmarks.htm')
        self.response.out.write(output)


class MyBookmarksHandler(BaseHandler):
    @login_required
    def get(self):
        nav = memcache.get('nav')
        if nav is None:
            nav = helper.create_nav_section(None)
            nav = '''<ul><li>
                    <a href="/my_bookmarks">My Bookmarks</a>
                    %s</li></ul>''' % (nav,)
            if not memcache.add('nav', nav, 3600):
                logging.error("Memcache set failed.")
        key = self.request.get('key', default_value=None)
        folder = db.get(key) if key else None
        query = Bookmark.gql(
            "WHERE bm_parent = :1 AND owner = :2 ORDER BY title",
            folder, users.get_current_user())
        context = {
            'nav': nav,
            'bookmarks': query,
            'current_folder_key': key if key else '',
            'current_folder_path': helper.get_folder_path(folder), 
        }
        self.render("my_bookmarks", context)
        

class AddBookmarkHandler(BaseHandler):
    @login_required
    def get(self):
        parent = self.get_parent()
        context = {
            "bm_title": "",
            "url": "",
            "shared": True if parent and parent.shared else False,
            "parent_key": str(parent.key()) if parent else "",
            "current_folder_path": helper.get_folder_path(parent),
        }
        self.render("add_bookmark", context)

    def post(self):
        input_data = {
            "bm_title": self.request.get(
                "bm_title", default_value="").strip(),
            "url": self.request.get(
                "url", default_value="").strip(),
            "shared": True if self.request.get(
                "shared", default_value=False) else False,
        }
        parent = self.get_parent()
        err_msg = helper.validate_bookmark_data(input_data)
        if err_msg:
            input_data["err_msg"] = err_msg
            input_data["current_folder_path"] = \
                    helper.get_folder_path(parent)
            self.render("add_bookmark", input_data)
            return
        bm_path = helper.get_bm_path(parent) 
        bm = Bookmark(
                title=input_data["bm_title"],
                url=input_data["url"],
                shared=input_data["shared"],
                is_folder=False,
                bm_parent=parent,
                bm_path=bm_path
        )
        bm.put()
        parent_key = str(parent.key()) if parent else ""
        self.redirect("/my_bookmarks?key=" + parent_key)

    def get_parent(self):
        parent_key = self.request.get(
            "parent_key", default_value=None)
        if not parent_key:
            return None
        return db.get(parent_key)


class EditBookmarkHandler(BaseHandler):
    @login_required
    def get(self):
        bm = self.get_bm()
        if bm is None:
            self.error(400)
        else: 
            self.render("edit_bookmark", \
                { "bm": bm, 
                  "err_msg": None,
                  "current_folder_path": helper.get_folder_path(bm.bm_parent), 
                }) 

    def post(self):
        bm = self.get_bm()
        if bm is None:
            self.error(400)
            return
        parent_key = str(bm.bm_parent.key()) if bm.bm_parent else ''
        if self.request.get("action") == "Delete":
            bm.delete()
            self.redirect("/my_bookmarks?key=" + parent_key)
            return
        data = {}
        data["bm_title"] = self.request.get("bm_title", default_value="")
        data["url"] = self.request.get("url", default_value="")
        data["shared"] = True if self.request.get(
            "shared", default_value=None) else False
        data["bm_parent"] = bm.bm_parent
        err_msg = helper.validate_bookmark_data(data)
        if not err_msg:
            bm.title = data["bm_title"]
            bm.url = data["url"]
            bm.shared = data["shared"]
            bm.put()
            self.redirect("/my_bookmarks?key=" + parent_key)
        else:
            self.render("edit_bookmark", \
                { "bm": data, 
                  "err_msg": err_msg,
                  "current_folder_path": helper.get_folder_path(bm.bm_parent),
                })

    def get_bm(self):
        key = self.request.get("key", default_value=None)
        if not key:
            return None
        return db.get(key)
    

class EditFolderHandler(BaseHandler):
    @login_required
    def get(self):
        folder = self.get_folder()
        if folder is None:
            self.error(400)
            return
        context = {
            "folder_name": folder.title,
            "shared": folder.shared,
            "key": str(folder.key()),
            "parent_key": str(folder.bm_parent.key()) \
                if folder.bm_parent else '',
            "err_msg": None,
            "current_folder_path": helper.get_folder_path(folder.bm_parent),
        }
        self.render("edit_folder", context)

    def get_folder(self):
        key = self.request.get("key", default_value=None)
        if not key:
            return None
        folder = db.get(key)
        return folder

    def post(self):
        folder = self.get_folder()
        if folder is None:
            self.error(400)
            return
        parent_key = str(folder.bm_parent.key()) \
            if folder.bm_parent else ''
        if self.request.get("action") == "Delete":
            helper.delete_folder(folder)
            memcache.delete("nav")
            self.redirect("/my_bookmarks?key=" + parent_key)
            return
        folder_name = self.request.get(
            "folder_name", default_value='').strip()
        shared = True if self.request.get(
            "shared", default_value=False) else False
        if not folder_name:
            err_msg = ["Folder name is required."]
            context = {
                "folder_name": folder_name,
                "shared": shared,
                "key": str(folder.key()),
                "parent_key": str(folder.bm_parent.key()),
                "err_msg": err_msg,
                "current_folder_path": 
                    helper.get_folder_path(folder.bm_parent),
            }
            self.render("edit_folder", context)
        else:
            folder.title = folder_name
            folder.shared = shared
            # shared property of all the bookmarks in the folder ???
            folder.put()
            self.redirect("/my_bookmarks?key=" + parent_key)


class AddFolderHandler(BaseHandler):
    @login_required
    def get(self):
        parent_folder = self.get_parent_folder()
        parent_key = ''
        if parent_folder:
            parent_key = str(parent_folder.key())
        shared = False
        if parent_folder and parent_folder.shared:
            shared = True
        context = {
            "folder_name": "",
            "shared": shared,
            "parent_key": parent_key,
            "err_msg": None,
            "current_folder_path":
                helper.get_folder_path(parent_folder),
        }
        self.render("add_folder", context)

    def get_parent_folder(self):
        parent_key = self.request.get("parent_key", default_value=None)
        if not parent_key:
            return None
        else:
            return db.get(parent_key)

    def post(self):
        parent = self.get_parent_folder()
        parent_key = ''
        if parent:
            parent_key = str(parent.key())
        folder_name = self.request.get(
            "folder_name", default_value='').strip()
        shared = True if self.request.get(
            "shared", default_value=False) else False
        if folder_name:
            folder = Bookmark(
                title=folder_name,
                url=None,
                is_folder=True,
                bm_parent=parent,
                shared=shared,
                bm_path=(parent.bm_path if parent else '') \
                    + '::' + folder_name.lower()
            )
            folder.put()
            memcache.delete("nav")
            self.redirect("/my_bookmarks?key=" + parent_key)
        else:
            err_msg = ["Folder name is required.",]
            current_folder_path = helper.get_folder_path(parent)
            self.render("add_folder", locals())


class BatchEditHandler(BaseHandler):
    def post(self):
        keys = []
        item_count = int(self.request.get(
                "item_count", default_value=0))
        for i in xrange(1, item_count+1):
            key = self.request.get("cb%s" % i)
            if key:
                keys.append(key)
        action = self.request.get("action")
        user = users.get_current_user()
        reload_nav = False
        if action == "Delete Checked":
            for key in keys:
                bm = db.get(key)
                if bm.owner != user:
                    self.error(403)
                    return
                if bm.is_folder:
                    helper.delete_folder(bm)
                    reload_nav = True
                else:
                    bm.delete()
            if reload_nav:
                memcache.delete("nav")
        parent_key = self.request.get(
            "current_folder_key", default_value="")
        self.redirect("/my_bookmarks?key=" + parent_key)


class DeleteAllBookmarksHandler(webapp.RequestHandler):
    def post(self):
        while True:
            query = db.GqlQuery(
                    "SELECT __key__ FROM Bookmark WHERE owner = :1",
                    users.get_current_user())
            if not query.count():
                break
            db.delete(query.fetch(200))
            time.sleep(0.5)

        memcache.delete("nav")
        self.redirect("/my_bookmarks")

