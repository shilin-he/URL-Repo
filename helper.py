import cgi
import urlparse
import urllib
from models import *
from google.appengine.api import users

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
            child_path = (parent.bm_path if parent else '') \
                    + '::' + child_title.lower().strip() 
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
            child_path = (parent.bm_path if parent else '') + '::****'
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


def export_bookmarks(parent, bookmarks):
    query = Bookmark.gql("WHERE bm_parent = :1 AND owner = :2", 
                parent, users.get_current_user())
    for bm in query:
        if bm.is_folder:
            folder = {"type": "text/x-moz-place-container",
                      "title": bm.title}
            bookmarks.setdefault("children", []).append(folder)
            export_bookmarks(bm, folder)
        else:
            bookmark = {"type": "text/x-moz-place",
                        "title": bm.title,
                        "uri": bm.url}
            bookmarks.setdefault("children", []).append(bookmark)
			
			
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


def get_bm_path(parent):
    return (parent.bm_path if parent else '') + '::****'


def get_folder_path(folder):
    if not folder:
        return "My bookmarks"
    else:
        temp = [i.title() for i in folder.bm_path.split("::")]
        return "My bookmarks" + " / ".join(temp)
