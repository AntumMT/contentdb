import datetime, json

from app.logic.LogicError import LogicError
from app.logic.uploads import upload_file
from app.models import User, Package, PackageScreenshot, Permission, NotificationType, db, AuditSeverity
from app.utils import addNotification, addAuditLog


def do_create_screenshot(user: User, package: Package, title: str, file, reason: str = None):
	thirty_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=30)
	count = package.screenshots.filter(PackageScreenshot.created_at > thirty_minutes_ago).count()
	if count >= 20:
		raise LogicError(429, "Too many requests, please wait before trying again")

	uploaded_url, uploaded_path = upload_file(file, "image", "a PNG or JPG image file")

	counter = 1
	for screenshot in package.screenshots.all():
		screenshot.order = counter
		counter += 1

	ss = PackageScreenshot()
	ss.package  = package
	ss.title    = title or "Untitled"
	ss.url      = uploaded_url
	ss.approved = package.checkPerm(user, Permission.APPROVE_SCREENSHOT)
	ss.order    = counter
	db.session.add(ss)

	if reason is None:
		msg = "Created screenshot {}".format(ss.title)
	else:
		msg = "Created screenshot {} ({})".format(ss.title, reason)

	addNotification(package.maintainers, user, NotificationType.PACKAGE_EDIT, msg, package.getURL("packages.view"), package)
	addAuditLog(AuditSeverity.NORMAL, user, msg, package.getURL("packages.view"), package)

	db.session.commit()

	return ss


def do_order_screenshots(_user: User, package: Package, order: [any]):
	lookup = {}
	for screenshot in package.screenshots.all():
		lookup[screenshot.id] = screenshot

	counter = 1
	for ss_id in order:
		try:
			lookup[int(ss_id)].order = counter
			counter += 1
		except KeyError as e:
			raise LogicError(400, "Unable to find screenshot with id={}".format(ss_id))
		except (ValueError, TypeError) as e:
			raise LogicError(400, "Invalid id, not a number: {}".format(json.dumps(ss_id)))

	db.session.commit()
