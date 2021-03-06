import secrets
import jwt

from fastapi import APIRouter, status, HTTPException, Request, BackgroundTasks
from starlette.responses import Response
from models.auth import *
from helper.config import *
from helper.authentication import *
from helper.email_helper import send_mail
from worker import send_mail_task

auth_router = APIRouter(
    prefix="/auth",
    tags=['auth']
)


@auth_router.post('/register', status_code=status.HTTP_201_CREATED)
async def register(data: userRegister_pydantic, request: Request, backgroundTasks: BackgroundTasks):
    user_info = data.dict(exclude_unset=True)
    user_info['password'] = User.get_hashed_password(user_info['password'])
    user_obj = await User.create(**user_info)

    d = {
        "id": user_obj.id,
    }
    token = jwt.encode(d, config['SECRET_KEY'], algorithm="HS256")
    domain = request.client.host
    link = f"http://{domain}:8000/auth/email-verify/?token={token}"
    body = f"""
        Hi {user_obj.name}, 
        Please use the link below to verify your account {link}
    """
    data = {
        "subject": "Verify your account",
        "body": body,
        "to": [user_obj.email]
    }
    send_mail_task.delay(data)
    # backgroundTasks.add_task(send_mail, data)

    return {"message": "We've sent you an email to verify your account"}


@auth_router.get('/email-verify', status_code=status.HTTP_200_OK)
async def email_verify(token: str):
    try:
        payload = jwt.decode(token, config['SECRET_KEY'], algorithms="HS256")
        user = await User.get(id=payload['id'])

        if user and not user.is_verified:
            user.is_verified = True
            await user.save()

        return {"message": "Successfully activate"}
    except jwt.exceptions.DecodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token, please request a new one", headers={"WWW-Authenticate": "Bearer"})
    except jwt.exceptions.ExpiredSignatureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is expired, please request a new one", headers={"WWW-Authenticate": "Bearer"})


@auth_router.post('/login', status_code=status.HTTP_200_OK)
async def login(data: userLogin_pydantic, Authorize: AuthJWT=Depends()):
    user_info = data.dict()
    user = await User.get(email=user_info['email'])
    if user and user.verify_password(user_info['password']):

        access_token = Authorize.create_access_token(subject=user.email, user_claims={"is_staff": user.is_staff})
        refresh_token = Authorize.create_refresh_token(subject=user.email)

        return {"access_token": access_token, "refresh_token": refresh_token}
    raise AUTH_EXCEPTION


@auth_router.post('/reset-password', status_code=status.HTTP_201_CREATED)
async def reset_password(data: userResetPassword_pydantic, request: Request, backgroundTasks: BackgroundTasks):
    email = data.dict()['email']

    user = await User.get(email=email)
    if user:
        d = {
            "id": user.id,
            "name": user.name
        }
        token = secrets.token_hex()
        uidb64 = create_signed_token(token.encode('utf-8'), d)
        domain = request.client.host
        link = f"http://{domain}:8000/auth/reset-password-confirm/{uidb64}/{token}/"
        body = f"""
            Hi {user.name},
            Please use the link below to reset your password {link}
        """
        data = {
            "subject": "Reset your password",
            "body": body,
            "to": [user.email]
        }
        send_mail_task.delay(data)
        # backgroundTasks.add_task(send_mail, data)

        return {"message": "We've sent you an email to reset your password"}
    raise AUTH_EXCEPTION


@auth_router.post('/reset-password-confirm/{uidb64}/{token}/', status_code=status.HTTP_200_OK)
async def reset_password_confirm(uidb64: str, token: str):
    (verified, payload) = verify_signed_token(token.encode('utf-8'), uidb64)

    if verified:
        return {"sucess": True, "uidb64": uidb64, "token": token}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is invalid or expired, please request a new one", headers={'WWW-Authenticate': "Bearer"})


@auth_router.post('/set-new-password', status_code=status.HTTP_202_ACCEPTED)
async def set_new_password(data: ResetPasswordModel):
    param = data.dict()
    (verified, payload) = verify_signed_token(param['token'].encode('utf-8'), param['uidb64'])

    if verified:
        user = await User.get(id=payload['id'])
        user.password = User.get_hashed_password(param['password'])
        await user.save()

        return {"message": "Change password successfully"}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is invalid or expired, please request a new one", headers={'WWW-Authenticate': "Bearer"})


@auth_router.post('/logout')
@validate_token
async def logout(Authorize:AuthJWT=Depends()):
    jti = Authorize.get_raw_jwt()['jti']
    redis_conn.setex(jti,settings.access_expires,'true')
    return Response(status_code=status.HTTP_204_NO_CONTENT)

