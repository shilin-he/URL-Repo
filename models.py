from google.appengine.ext import db


class Bookmark(db.Model):
    title = db.StringProperty(required=True)
    url = db.LinkProperty()
    is_folder = db.BooleanProperty(required=True)
    bm_parent = db.SelfReferenceProperty(
        collection_name='children')
    bm_path = db.StringProperty(required=True)
    owner = db.UserProperty(required=True, auto_current_user_add=True)
    shared = db.BooleanProperty(required=True, default=False)

