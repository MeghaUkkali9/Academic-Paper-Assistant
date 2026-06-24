from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import logging

class User(BaseModel):
    id: int
    name:str
    age:int
    salary: Optional[float]
    
class UserCreate(BaseModel):
    name:str = Field(min_length=4)
    age:int = Field(gt=0)
    salary: Optional[float] = Field(default=None, ge=0)
    
class UserResponse(BaseModel):
    id:int
    name:str
    age:int
    salary: Optional[float]
    
class UserUpdate(BaseModel):
    name:str
    age:int
    salary: Optional[float]
    
user_router = APIRouter(tags=["user api"], prefix="/user")
logger = logging.getLogger(__name__)


class NotFoundUserException(Exception):
    """User not found"""
    
dict_: Dict[int, User] = {}
id_ = 0

@user_router.get("/", response_model=List[UserResponse])
async def get_all_users():
    user_list = []
    
    for user in dict_.values():
        user_res = UserResponse(
            id = user.id, 
            name = user.name,
            age = user.age,
            salary = user.salary
        )
        user_list.append(user_res)
    return user_list
    
@user_router.post("/", response_model=UserResponse)
async def create_user(user:UserCreate):
    try:
        global id_
        id_ += 1
        created_user = User(
            id = id_,
            name = user.name,
            age = user.age,
            salary = user.salary
        )
        dict_[id_] = created_user
        logger.info("User created successfully")
        
        return created_user
    except Exception as e:
        id_ -= 1
        logger.exception("Unexpected error occured")
        raise
    
@user_router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id:int, user:UserUpdate):
    try:
        if user_id not in dict_:
            raise HTTPException(
                status_code = 404,
                detail = "user not found"
            )
        
        saved_user = dict_[user_id]
        saved_user.name = user.name
        saved_user.age = user.age
        saved_user.salary = user.salary
        
        logger.info("updated user succesfully")
        return saved_user
    except Exception as e:
        logger.exception("Unexpected error")
        raise
    
@user_router.delete("/{user_id}")
async def delete_user(user_id: int):
    try:
        if user_id not in dict_:
            raise HTTPException(
                status_code = 404,
                detail = "User not found"
            )
        
        dict_.pop(user_id)
        
        logger.info("deleted user succesfully")
        
        return {"deleted_user_id": user_id}
    except Exception as e:
        logger.exception("Unexpected error")
        raise
    
# to run this service: docker compose -d up --build api

