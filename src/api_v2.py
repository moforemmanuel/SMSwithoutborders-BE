import logging
logger = logging.getLogger(__name__)

# configurations
from settings import Configurations
cookie_name = Configurations.COOKIE_NAME
ENABLE_RECAPTCHA = Configurations.ENABLE_RECAPTCHA
enable_otp_counter = Configurations.ENABLE_OTP

from flask import Blueprint
from flask import request
from flask import Response
from flask import jsonify

from src.protocolHandler import OAuth2, TwoFactor

from src.security.cookie import Cookie
from src.security.data import Data
from src.security.password_policy import password_check

import json
from datetime import datetime
from datetime import timedelta

from src.models.grants import Grant_Model
from src.models.users import User_Model
from src.models.sessions import Session_Model
from src.models._2FA import OTP_Model

from src.schemas.db_connector import db

v2 = Blueprint("v2", __name__)

from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import Conflict
from werkzeug.exceptions import Unauthorized
from werkzeug.exceptions import Forbidden
from werkzeug.exceptions import InternalServerError
from werkzeug.exceptions import TooManyRequests
from werkzeug.exceptions import UnprocessableEntity

@v2.before_request
def before_request():
    db.connect()

@v2.after_request
def after_request(response):
    db.close()
    
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubdomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "script-src 'self'; object-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Permissions-Policy"] = "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), clipboard-read=(), clipboard-write=(), cross-origin-isolated=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), speaker=(), speaker-selection=(), sync-xhr=(), usb=(), web-share=(), xr-spatial-tracking=()"

    return response

@v2.route("/signup", methods=["POST", "PUT"])
def signup():
    """
    """
    try:
        method = request.method

        User = User_Model()
        Session = Session_Model()
        data = Data()
        cookie = Cookie()

        if method.lower() == "post":
            if not "phone_number" in request.json or not request.json["phone_number"]:
                logger.error("no phone_number")
                raise BadRequest()
            elif not "country_code" in request.json or not request.json["country_code"]:
                logger.error("no country_code")
                raise BadRequest()
            elif not "password" in request.json or not request.json["password"]:
                logger.error("no password")
                raise BadRequest()

            user_agent = request.headers.get("User-Agent")

            phone_number = request.json["phone_number"]
            name = request.json["name"]
            country_code = request.json["country_code"]
            password = request.json["password"]

            password_check(password=password)

            user_id = User.create(
                phone_number=phone_number,
                name=name,
                country_code=country_code,
                password=password
            )

            res = jsonify({
                "uid": user_id
            })

            session = Session.create(
                unique_identifier=data.hash(country_code+phone_number),
                user_agent=user_agent,
                type="signup",
            )

            cookie_data = json.dumps({
                "sid": session["sid"],
                "cookie": session["data"],
                "type":session["type"]
            })
            e_cookie = cookie.encrypt(cookie_data)

            session_data = json.loads(session["data"])

            res.set_cookie(
                cookie_name,
                e_cookie,
                max_age=timedelta(milliseconds=session_data["maxAge"]),
                secure=session_data["secure"],
                httponly=session_data["httpOnly"],
                samesite=session_data["sameSite"]
            )

        elif method.lower() == "put":
            if not request.cookies.get(cookie_name):
                logger.error("no cookie")
                raise Unauthorized()
            elif not request.headers.get("User-Agent"):
                logger.error("no user agent")
                raise BadRequest()

            e_cookie = request.cookies.get(cookie_name)
            d_cookie = cookie.decrypt(e_cookie)
            json_cookie = json.loads(d_cookie)

            sid = json_cookie["sid"]
            uid = json_cookie["uid"]
            unique_identifier = json_cookie["unique_identifier"]
            user_cookie = json_cookie["cookie"]
            type = json_cookie["type"]
            status = json_cookie["status"]
            user_agent = request.headers.get("User-Agent")

            Session.find(
                sid=sid,
                unique_identifier=unique_identifier,
                user_agent=user_agent,
                cookie=user_cookie,
                type=type,
                status=status
            )

            User.update(
                user_id=uid,
                status="verified"
            )

            Session.update(
                sid=sid,
                unique_identifier=unique_identifier,
                status="verified",
                type=type
            )

            res = Response()

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/recovery", methods=["POST"])
def recovery():
    """
    """
    try:
        User = User_Model()
        Session = Session_Model()
        data = Data()
        cookie = Cookie()

        if not "phone_number" in request.json or not request.json["phone_number"]:
            logger.error("no phone_number")
            raise BadRequest()
        
        user_agent = request.headers.get("User-Agent")

        phone_number = request.json["phone_number"]
    
        user = User.find(phone_number=phone_number)

        res = jsonify({
            "uid": user["userId"]
        })

        session = Session.create(
            unique_identifier=data.hash(phone_number),
            user_agent=user_agent,
            type="recovery",
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"],
            "type":session["type"]
        })
        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/recovery", methods=["PUT"])
async def recovery_check(user_id):
    """
    """
    try:
        originUrl = request.headers.get("Origin")
        Grant = Grant_Model()
        data = Data()

        User = User_Model()
        Session = Session_Model()
        cookie = Cookie()

        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        unique_identifier = json_cookie["unique_identifier"]
        user_cookie = json_cookie["cookie"]
        type = json_cookie["type"]
        status = json_cookie["status"]
        user_agent = request.headers.get("User-Agent")

        new_password = request.json["new_password"]

        Session.find(
            sid=sid,
            unique_identifier=unique_identifier,
            user_agent=user_agent,
            cookie=user_cookie,
            type=type,
            status=status
        )

        wallets = Grant.find_all(user_id=user_id)

        for wallet in wallets:
            grant = Grant.find(user_id=user_id, platform_id=wallet["platformId"])
            d_grant = Grant.decrypt(grant=grant)

            Grant.purge(
                originUrl=originUrl,
                identifier="",
                platform_name=wallet["platformId"],
                token=d_grant["token"]
            )

            Grant.delete(grant=grant)

        User.update(
            user_id=user_id,
            password=data.hash(new_password)
        )

        Session.update(
            sid=sid,
            unique_identifier=unique_identifier,
            status="updated",
            type=type
        )

        res = Response()

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/login", methods=["POST"])
def signin():
    """
    """
    try:
        User = User_Model()
        Session = Session_Model()
        cookie = Cookie()

        if not "phone_number" in request.json or not request.json["phone_number"]:
            logger.error("no phone_number")
            raise BadRequest()
        elif not "password" in request.json or not request.json["password"]:
            logger.error("no password")
            raise BadRequest()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()

        if ENABLE_RECAPTCHA:
            if not "captcha_token" in request.json or not request.json["captcha_token"]:
                logger.error("no captcha_token")
                raise BadRequest()

            captcha_token = request.json["captcha_token"]
            remote_ip = request.remote_addr

            User.recaptcha(captchaToken=captcha_token, remoteIp=remote_ip)

        user_agent = request.headers.get("User-Agent")

        phone_number = request.json["phone_number"]
        password = request.json["password"]

        user = User.verify(
            phone_number=phone_number,
            password=password
        )

        res = jsonify({
            "uid": user["userId"]
        })

        session = Session.create(
            unique_identifier=user["userId"],
            user_agent=user_agent
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"]
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/OTP", methods=["POST"])
def OTP(user_id):
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()
        elif not "phone_number" in request.json or not request.json["phone_number"]:
            logger.error("no phone_number")
            raise BadRequest()

        Session = Session_Model()
        data = Data()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        type = json_cookie["type"]
        user_agent = request.headers.get("User-Agent")

        phone_number = request.json["phone_number"]

        phone_number_hash = data.hash(phone_number)
    
        Session.find(
            sid=sid,
            unique_identifier=phone_number_hash,
            user_agent=user_agent,
            cookie=user_cookie,
            type=type
        )

        otp = OTP_Model(phone_number=phone_number)

        cid = None
        expires = 0

        if enable_otp_counter:
            otp_counter = otp.check_count(
                unique_id=phone_number_hash,
                user_id=user_id
            )         

            cid = otp_counter.id

        otp_res = otp.verification()

        if otp_res.status == "pending":
            if enable_otp_counter:
                expires = otp.add_count(otp_counter)

            res = jsonify({
                "expires": int(round(expires)) * 1000
            })
        else:
            logger.error("OTP FAILED with status '%s'" % otp_res.status)
            raise InternalServerError(otp_res)

        session = Session.update(
            sid=sid,
            unique_identifier=phone_number_hash,
            type=type
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "uid": user_id,
            "cookie": session["data"],
            "type": session["type"],
            "phone_number": phone_number,
            "cid": cid
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 201
                
    except BadRequest as err:
        return str(err), 400

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409
    
    except TooManyRequests as err:
        return str(err), 429

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/OTP", methods=["PUT"])
def OTP_check():
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()
        elif not "code" in request.json or not request.json["code"]:
            logger.error("no code")
            raise BadRequest()

        Session = Session_Model()
        data = Data()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        uid = json_cookie["uid"]
        user_cookie = json_cookie["cookie"]
        type = json_cookie["type"]
        phone_number = json_cookie["phone_number"]
        cid = json_cookie["cid"]
        user_agent = request.headers.get("User-Agent")

        code = request.json["code"]

        phone_number_hash = data.hash(phone_number)
    
        Session.find(
            sid=sid,
            unique_identifier=phone_number_hash,
            user_agent=user_agent,
            cookie=user_cookie,
            type=type
        )

        otp = OTP_Model(phone_number=phone_number)

        otp_res = otp.verification_check(code=code)

        if otp_res.status == "approved":
            if enable_otp_counter:
                otp.delete_count(counter_id=cid)
                
            res = Response()
        elif otp_res.status == "pending":
            logger.error("Invalid OTP code. OTP_check status = %s" % otp_res.status)
            raise Forbidden()
        else:
            logger.error("OTP_check FAILED with status '%s'" % otp_res.status)
            raise InternalServerError(otp_res)

        session = Session.update(
            sid=sid,
            unique_identifier=phone_number_hash,
            status="success",
            type=type
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "unique_identifier": session["uid"],
            "uid": uid,
            "cookie": session["data"],
            "status": "success",
            "type": type
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except Forbidden as err:
        return str(err), 403

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("users/<string:user_id>/platforms/<string:platform>/protocols/<string:protocol>", defaults={"action": None}, methods=["POST", "PUT", "DELETE"])
@v2.route("users/<string:user_id>/platforms/<string:platform>/protocols/<string:protocol>/<string:action>", methods=["PUT"])
def manage_grant(user_id, platform, protocol, action) -> dict:
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()

        originUrl = request.headers.get("Origin")
        method = request.method
        
        Session = Session_Model()
        User = User_Model()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        user_agent = request.headers.get("User-Agent")

        Session.find(
            sid=sid,
            unique_identifier=user_id,
            user_agent=user_agent,
            cookie=user_cookie
        )

        code = request.json.get("code")
        scope = request.json.get("scope")
        phone_number = request.json.get("phone_number")
        code_verifier = request.json.get("code_verifier")
        first_name = request.json.get("first_name")
        last_name = request.json.get("last_name")

        Grant = Grant_Model()

        if protocol == "oauth2":
            Protocol = OAuth2(origin=originUrl, platform_name=platform)
        elif protocol == "twofactor":
            Protocol = TwoFactor(identifier=phone_number or "", platform_name=platform)

        if method.lower() == "post":
            result = Protocol.authorization()

            url = result.get("url") or ""
            code_verifier = result.get("code_verifier") or ""
            body = result.get("body") or ""

            res = jsonify({
                "url": url,
                "code_verifier": code_verifier,
                "body": body,
                "platform": platform.lower()
            })

        elif method.lower() == "put":      
            if action == "register":
                result = Protocol.registration(
                    first_name=first_name,
                    last_name=last_name
                )

            else:
                result = Protocol.validation(
                    code=code,
                    scope=scope,
                    code_verifier=code_verifier
                )

            body = result.get("body") or ""
            initialization_url = result.get("initialization_url") or ""
            grant = result.get("grant")

            if grant:
                Grant.store(
                    user_id=user_id,
                    platform_id=platform.lower(),
                    grant=grant
                )
          
            res = jsonify({
                "body": body,
                "initialization_url": initialization_url
            })

        elif method.lower() == "delete":
            if not request.json.get("password"):
                logger.error("no password")
                raise BadRequest()

            password = request.json.get("password")

            try:
                user = User.verify(user_id=user_id, password=password)
            except Unauthorized:
                raise Forbidden()

            grant = Grant.find(user_id=user["id"], platform_id=platform.lower())
            d_grant = Grant.decrypt(grant=grant)
            
            Protocol.invalidation(token=d_grant["token"])

            Grant.delete(grant=grant)

            res = Response()

        session = Session.update(
            sid=sid,
            unique_identifier=user_id
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"]
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200

    except BadRequest as error:
        return str(error), 400

    except Conflict as error:
        return str(error), 409

    except Unauthorized as error:
        return str(error), 401

    except Forbidden as error:
        return str(error), 403

    except TooManyRequests as error:
        return str(error), 429

    except UnprocessableEntity as error:
        return str(error), 422
        
    except InternalServerError as error:
        logger.exception(error)
        return "internal server error", 500

    except Exception as error:
        logger.exception(error)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/platforms", methods=["GET"])
def get_platforms(user_id):
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()

        Session = Session_Model()
        User = User_Model()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        user_agent = request.headers.get("User-Agent")
    
        Session.find(
            sid=sid,
            unique_identifier=user_id,
            user_agent=user_agent,
            cookie=user_cookie
        )

        user_platforms = User.find_platform(user_id=user_id)

        res = jsonify(user_platforms)

        session = Session.update(
            sid=sid,
            unique_identifier=user_id
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"]
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/dashboard", methods=["GET"])
def dashboard(user_id):
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()

        Session = Session_Model()
        User = User_Model()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        user_agent = request.headers.get("User-Agent")
    
        Session.find(
            sid=sid,
            unique_identifier=user_id,
            user_agent=user_agent,
            cookie=user_cookie
        )

        user = User.find(user_id=user_id)

        result = {
            "createdAt": user["createdAt"],
            "updatedAt": user["last_login"] if user["last_login"] else datetime.now()
        }

        res = jsonify(result)

        session = Session.update(
            sid=sid,
            unique_identifier=user_id
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"]
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/password", methods=["POST"])
async def update_password(user_id):
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()
        elif not "password" in request.json or not request.json["password"]:
            logger.error("no password")
            raise BadRequest()
        elif not "new_password" in request.json or not request.json["new_password"]:
            logger.error("no new_password")
            raise BadRequest()

        originUrl = request.headers.get("Origin")
        Grant = Grant_Model()
        Session = Session_Model()
        User = User_Model()
        data = Data()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        user_agent = request.headers.get("User-Agent")

        password = request.json["password"]
        new_password = request.json["new_password"]
    
        Session.find(
            sid=sid,
            unique_identifier=user_id,
            user_agent=user_agent,
            cookie=user_cookie
        )

        try:
            user = User.verify(user_id=user_id, password=password)
        except Unauthorized:
            raise Forbidden()

        wallets = Grant.find_all(user_id=user["id"])

        for wallet in wallets:
            grant = Grant.find(user_id=user_id, platform_id=wallet["platformId"])
            d_grant = Grant.decrypt(grant=grant)

            Grant.purge(
                originUrl=originUrl,
                identifier="",
                platform_name=wallet["platformId"],
                token=d_grant["token"]
            )

            Grant.delete(grant=grant)

        User.update(
            user_id=user["id"],
            password=data.hash(new_password)
        )

        res = Response()

        session = Session.update(
            sid=sid,
            unique_identifier=user_id
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"]
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Forbidden as err:
        return str(err), 403

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/verify", methods=["POST"])
def verify_user_id(user_id):
    """
    """
    try:
        if not "password" in request.json or not request.json["password"]:
            logger.error("no password")
            raise BadRequest()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()

        Session = Session_Model()
        User = User_Model()
        cookie = Cookie()

        user_agent = request.headers.get("User-Agent")

        password = request.json["password"]

        user = User.verify(
            user_id=user_id,
            password=password
        )

        res = Response()

        session = Session.create(
            unique_identifier=user["id"],
            user_agent=user_agent
        )

        cookie_data = json.dumps({
            "sid": session["sid"],
            "cookie": session["data"]
        })

        e_cookie = cookie.encrypt(cookie_data)

        session_data = json.loads(session["data"])

        res.set_cookie(
            cookie_name,
            e_cookie,
            max_age=timedelta(milliseconds=session_data["maxAge"]),
            secure=session_data["secure"],
            httponly=session_data["httpOnly"],
            samesite=session_data["sameSite"]
        )

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>/logout", methods=["POST"])
def logout(user_id):
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()
    
        Session = Session_Model()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        user_agent = request.headers.get("User-Agent")
    
        Session.find(
            sid=sid,
            unique_identifier=user_id,
            user_agent=user_agent,
            cookie=user_cookie
        )
                
        res = Response()

        res.delete_cookie(cookie_name)

        logger.info("- Successfully cleared cookie")

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Forbidden as err:
        return str(err), 403

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500

@v2.route("/users/<string:user_id>", methods=["DELETE"])
async def delete_account(user_id):
    """
    """
    try:
        if not request.cookies.get(cookie_name):
            logger.error("no cookie")
            raise Unauthorized()
        elif not request.headers.get("User-Agent"):
            logger.error("no user agent")
            raise BadRequest()
        elif not "password" in request.json or not request.json["password"]:
            logger.error("no password")
            raise BadRequest()

        originUrl = request.headers.get("Origin")
        Grant = Grant_Model()
        Session = Session_Model()
        User = User_Model()
        cookie = Cookie()

        e_cookie = request.cookies.get(cookie_name)
        d_cookie = cookie.decrypt(e_cookie)
        json_cookie = json.loads(d_cookie)

        sid = json_cookie["sid"]
        user_cookie = json_cookie["cookie"]
        user_agent = request.headers.get("User-Agent")

        password = request.json["password"]
    
        Session.find(
            sid=sid,
            unique_identifier=user_id,
            user_agent=user_agent,
            cookie=user_cookie
        )

        try:
            user = User.verify(user_id=user_id, password=password)
        except Unauthorized:
            raise Forbidden()

        wallets = Grant.find_all(user_id=user["id"])

        for wallet in wallets:
            grant = Grant.find(user_id=user_id, platform_id=wallet["platformId"])
            d_grant = Grant.decrypt(grant=grant)

            Grant.purge(
                originUrl=originUrl,
                identifier="",
                platform_name=wallet["platformId"],
                token=d_grant["token"]
            )

            Grant.delete(grant=grant)

        User.delete(
            user_id=user["id"]
        )

        Session.create(
            unique_identifier=user["id"],
            user_agent=user_agent,
            type="deleted"
        )

        res = Response()

        return res, 200
                
    except BadRequest as err:
        return str(err), 400

    except TooManyRequests as err:
        return str(err), 429

    except Unauthorized as err:
        return str(err), 401

    except Forbidden as err:
        return str(err), 403

    except Conflict as err:
        return str(err), 409

    except InternalServerError as err:
        logger.exception(err)
        return "internal server error", 500

    except Exception as err:
        logger.exception(err)
        return "internal server error", 500