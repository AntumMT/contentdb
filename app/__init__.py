# ContentDB
# Copyright (C) 2018-21  rubenwardy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


from flask import *
from flask_gravatar import Gravatar
import flask_menu as menu
from flask_mail import Mail
from flask_github import GitHub
from flask_wtf.csrf import CSRFProtect
from flask_flatpages import FlatPages
from flask_babel import Babel
from flask_login import logout_user, current_user, LoginManager
import os, redis

app = Flask(__name__, static_folder="public/static")
app.config["FLATPAGES_ROOT"] = "flatpages"
app.config["FLATPAGES_EXTENSION"] = ".md"
app.config["FLATPAGES_MARKDOWN_EXTENSIONS"] = ["fenced_code", "tables", "codehilite", 'toc']
app.config["FLATPAGES_EXTENSION_CONFIG"] = {
	"fenced_code": {},
	"tables": {},
	"codehilite": {
		"guess_lang": False,
	}
}
app.config.from_pyfile(os.environ["FLASK_CONFIG"])

r = redis.Redis.from_url(app.config["REDIS_URL"])

menu.Menu(app=app)
github = GitHub(app)
csrf = CSRFProtect(app)
mail = Mail(app)
pages = FlatPages(app)
babel = Babel(app)
gravatar = Gravatar(app,
		size=64,
		rating="g",
		default="retro",
		force_default=False,
		force_lower=False,
		use_ssl=True,
		base_url=None)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "users.login"

from .sass import sass
sass(app)


if not app.debug and app.config["MAIL_UTILS_ERROR_SEND_TO"]:
	from .maillogger import build_handler
	app.logger.addHandler(build_handler(app))


from app.utils.markdown import init_app
init_app(app)

# @babel.localeselector
# def get_locale():
# 	return request.accept_languages.best_match(app.config["LANGUAGES"].keys())

from . import models, template_filters

@login_manager.user_loader
def load_user(user_id):
	return models.User.query.filter_by(username=user_id).first()


from .blueprints import create_blueprints
create_blueprints(app)

@app.route("/uploads/<path:path>")
def send_upload(path):
	return send_from_directory(app.config["UPLOAD_DIR"], path)

@menu.register_menu(app, ".help", "Help", order=19, endpoint_arguments_constructor=lambda: { "path": "help" })
@app.route("/<path:path>/")
def flatpage(path):
	page = pages.get_or_404(path)
	template = page.meta.get("template", "flatpage.html")
	return render_template(template, page=page)

@app.before_request
def check_for_ban():
	if current_user.is_authenticated:
		if current_user.rank == models.UserRank.BANNED:
			flash("You have been banned.", "danger")
			logout_user()
			return redirect(url_for("users.login"))
		elif current_user.rank == models.UserRank.NOT_JOINED:
			current_user.rank = models.UserRank.MEMBER
			models.db.session.commit()

from .utils import clearNotifications

@app.before_request
def check_for_notifications():
	if current_user.is_authenticated:
		clearNotifications(request.path)

@app.errorhandler(404)
def page_not_found(e):
	return render_template("404.html"), 404
