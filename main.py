#!/usr/bin/env python
# -*- coding: utf-8 -*-

import webapp2
from handlers import *


url_mappings = [
    ('/', MainHandler),
    ('/import', ImportHandler),
    ('/export_html', ExportHTMLHandler),
    ('/export_json', ExportJSONHandler),
    ('/del_all', DeleteAllBookmarksHandler),
    ('/my_bookmarks', MyBookmarksHandler),
    ('/add_bookmark', AddBookmarkHandler),
    ('/edit_bookmark', EditBookmarkHandler),
    ('/add_folder', AddFolderHandler),
    ('/edit_folder', EditFolderHandler),
    ('/batch_edit', BatchEditHandler),
]

app = webapp2.WSGIApplication(url_mappings, debug=True)

