from fastapi import FastAPI, Depends
from fastapi_jwt_auth import AuthJWT
from tortoise.contrib.fastapi import register_tortoise
from helper.authentication import validate_token

from helper.config import config
from routers.auth_router import auth_router


app = FastAPI()

register_tortoise(
    app,
    db_url=config['DATABASE_URL'],
    modules={"models": ['models.auth']}, 
    generate_schemas=True,
    add_exception_handlers=True
)

app.include_router(auth_router)

@app.get('/')
@validate_token
def index(Authorize:AuthJWT=Depends()):
    return {"message": "Hello World"}