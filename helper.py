import cgi
import urlparse
import urllib
from HTMLParser import HTMLParser
from models import *
from google.appengine.api import users
from django.utils import simplejson


json = simplejson


def save_bookmarks(data, parent):
    for child in data.get('children', []):
        child_type = child.get('type')
        child_title = child.get('title', '')
        child_url = child.get('uri', '')
        scheme, netloc, path, query, fragment = \
                urlparse.urlsplit(child_url)
        if not scheme or not netloc:
            child_url = None
        
        if child_type == u'text/x-moz-place-container':
            child_path = get_bm_path(parent, title=child_title) 
            query = Bookmark.gql("WHERE bm_path = :1 AND owner = :2", 
                        child_path, users.get_current_user()).fetch(1)
            bm = query.pop() if query else None
            if not bm:
                bm = Bookmark(bm_parent=parent,
                              is_folder=True,
                              bm_path = child_path,
                              title=child_title,
                              url=child_url)
                bm.put()
            save_bookmarks(child, bm)
        elif child_type == u'text/x-moz-place':
            child_path = get_bm_path(parent, is_folder=False) 
            query = Bookmark.gql( \
                "WHERE bm_path = :1 AND title = :2 AND owner = :3",
                child_path, child_title, users.get_current_user()).fetch(1)
            bm = query.pop() if query else None
            if not bm and child_url:
                bm = Bookmark(bm_parent=parent,
                              is_folder=False,
                              bm_path = child_path,
                              title=child_title,
                              url=child_url)
                bm.put()


def export_to_firefox_json_format():
    bookmarks = {"title": "Bookmarks Menu",
                 "type": "text/x-moz-place-container",
                 "root": "bookmarksMenuFolder"}
    export_json(None, bookmarks)
    bookmarks = {"title": "",
                 "type": "text/x-moz-place-container",
                 "root": "placesRoot",
                 "children": [bookmarks,]}
    output = json.dumps(bookmarks)
    return output


def export_json(parent, bookmarks):
    query = Bookmark.gql("WHERE bm_parent = :1 AND owner = :2", 
                parent, users.get_current_user())
    for bm in query:
        if bm.is_folder:
            folder = {"type": "text/x-moz-place-container",
                      "title": bm.title}
            bookmarks.setdefault("children", []).append(folder)
            export_json(bm, folder)
        else:
            bookmark = {"type": "text/x-moz-place",
                        "title": bm.title,
                        "uri": bm.url}
            bookmarks.setdefault("children", []).append(bookmark)


def export_to_netscape_format():
    data = """
<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
It will be read and overwritten.
Do Not Edit! -->
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
"""
    return data + export_html(None) 


def export_html(parent):
    bookmarks = "<DL><p>"
    query = Bookmark.gql("WHERE bm_parent = :1 AND owner = :2", 
                parent, users.get_current_user())
    for bm in query:
        if bm.is_folder:
            bookmarks += "<DT><H3 FOLDED>%s</H3>" % (bm.title,)
            bookmarks += export_html(bm) 
        else:
            bookmarks += '<DT><A HREF="%s">%s</A>' % (bm.url, bm.title)

    bookmarks += "</DL><p>"
    return bookmarks
   
			
			
def validate_bookmark_data(data):
    err_msg = []
    if not data["bm_title"]:
        err_msg.append("Title is required.")
    if not data["url"]:
        err_msg.append("URL is required.")
    else:
        scheme, netloc, path, query, fragment = \
            urlparse.urlsplit(data["url"])
        if not scheme or not netloc:
            err_msg.append("Invalid URL.")
    return err_msg
	
	
def delete_folder(folder):
    query = Bookmark.gql(
        "WHERE bm_parent = :1 AND owner = :2 ORDER BY title", 
        folder, users.get_current_user())
    for bm in query:
        if bm.is_folder:
            delete_folder(bm)
        else:
            bm.delete()
    folder.delete()


def create_nav_section(parent):
    query = Bookmark.gql(
        "WHERE bm_parent = :1 AND owner = :2 ORDER BY title", 
        parent, users.get_current_user())
    temp = ""
    for bm in query:
        if bm.is_folder:
            href = "/my_bookmarks" + "?" + \
                       urllib.urlencode([("key", str(bm.key()))])
            title = cgi.escape(bm.title)    
            temp += '<li><a href="%s">%s</a>%s</li>' % \
                (href, title, create_nav_section(bm))
    if temp:
        temp = "<ul>%s</ul>" % (temp,) 
        return temp
    else:
        return ""


def get_bm_path(parent, is_folder=True, title=''):
    parent_bm_path = parent.bm_path if parent else ""
    if is_folder:
        return parent_bm_path + "::" + title.lower().strip()
    else:
        return parent_bm_path + "::****" 


def get_folder_path(folder):
    if not folder:
        return "My bookmarks"
    else:
        temp = [i.title() for i in folder.bm_path.split("::")]
        return "My bookmarks" + " / ".join(temp)


class NetscapeBookmarkParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.last_tag = '' 
        self.parent = None
        self.item = None
        self.user = users.get_current_user()

    def handle_starttag(self, tag, attrs):
        if tag == 'h3':
            self.item = Bookmark(
                            title="***",
                            url=None,
                            is_folder=True,
                            bm_parent=self.parent,
                            bm_path="***")

        if tag == 'a':
            url = ''
            for name, val in attrs:
                if name == 'href':
                    url = val
                    break
            self.item = Bookmark(
                            title="***",
                            url=url,
                            is_folder=False,
                            bm_parent=self.parent,
                            bm_path="***")

        if tag == 'dl' and self.last_tag == 'h3':
            self.parent = self.item

        self.last_tag = tag

    def handle_endtag(self, tag):
        if tag == 'dl' and self.last_tag in ['h3', 'a']:
            self.parent = self.parent.bm_parent if self.parent else None

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return
        if self.last_tag == 'h3':
            self.item.title = data
            self.item.bm_path = get_bm_path(self.parent, title=data) 
            query = Bookmark.gql(
                "WHERE bm_path = :1 AND owner = :2", 
                self.item.bm_path, self.user).fetch(1)
            bm = query.pop() if query else None
            if not bm:
                self.item.save()
            else:
                self.item = bm
        elif self.last_tag == 'a':
            self.item.title = data
            self.item.bm_path = get_bm_path(self.parent, is_folder=False) 
            query = Bookmark.gql(
                "WHERE bm_path = :1 AND title = :2 AND owner = :3", 
                self.item.bm_path, data, self.user).fetch(1)
            bm = query.pop() if query else None
            if not bm:
                self.item.save()
            else:
                self.item = bm
            

            
