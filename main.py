#!/usr/bin/env python


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from handlers import *


def main():
    url_mappings = [
        ('/', MainHandler),
        ('/import', ImportHandler),
        ('/export', ExportHandler),
        ('/del_all', DeleteAllBookmarksHandler),
        ('/my_bookmarks', MyBookmarksHandler),
        ('/add_bookmark', AddBookmarkHandler),
        ('/edit_bookmark', EditBookmarkHandler),
        ('/add_folder', AddFolderHandler),
        ('/edit_folder', EditFolderHandler),
        ('/batch_edit', BatchEditHandler),
    ]
    app = webapp.WSGIApplication(url_mappings, debug=True)
    util.run_wsgi_app(app)


if __name__ == '__main__':
    main()
