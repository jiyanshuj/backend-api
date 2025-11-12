"""
User management module for WanderEase
Handles user registration, profile management, and liked items
"""

from typing import Optional, Dict, List
from datetime import datetime
import db as database_module
from pymongo.errors import DuplicateKeyError

def get_db():
    """Get database instance"""
    return database_module.db

def serialize_doc(doc):
    """Use the serialize_doc function from db module"""
    return database_module.serialize_doc(doc)

def create_user(clerk_id: str, name: str, email: str, phone: Optional[str] = None) -> Dict:
    """
    Create a new user in the database
    
    Args:
        clerk_id: Clerk authentication ID (primary key)
        name: User's full name
        email: User's email address
        phone: User's phone number (optional)
    
    Returns:
        Created user document
    """
    db = get_db()
    
    user_doc = {
        "clerk_id": clerk_id,
        "name": name,
        "email": email,
        "phone": phone,
        "liked": {
            "tourism": [],
            "restaurants": [],
            "hotels": []
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    try:
        db.users.insert_one(user_doc)
        print(f"✅ User created: {name} ({clerk_id})")
        return serialize_doc(user_doc)
    except DuplicateKeyError:
        raise ValueError(f"User with clerk_id {clerk_id} already exists")


def get_user_by_clerk_id(clerk_id: str) -> Optional[Dict]:
    """Get user by Clerk ID"""
    db = get_db()
    user = db.users.find_one({"clerk_id": clerk_id})
    return serialize_doc(user) if user else None


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    db = get_db()
    user = db.users.find_one({"email": email})
    return serialize_doc(user) if user else None


def update_user(clerk_id: str, **updates) -> Optional[Dict]:
    """
    Update user information
    
    Args:
        clerk_id: User's Clerk ID
        **updates: Fields to update (name, email, phone)
    
    Returns:
        Updated user document
    """
    db = get_db()
    
    allowed_fields = ["name", "email", "phone"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    
    if not update_data:
        raise ValueError("No valid fields to update")
    
    update_data["updated_at"] = datetime.utcnow()
    
    result = db.users.find_one_and_update(
        {"clerk_id": clerk_id},
        {"$set": update_data},
        return_document=True
    )
    
    if result:
        print(f"✅ User updated: {clerk_id}")
        return serialize_doc(result)
    return None


def add_liked_item(clerk_id: str, category: str, item_id: str, item_data: Dict) -> Optional[Dict]:
    """
    Add an item to user's liked list
    
    Args:
        clerk_id: User's Clerk ID
        category: Category (tourism, restaurants, hotels)
        item_id: ID of the item (place_id, restaurant_id, hotel_id)
        item_data: Basic item information to store
    
    Returns:
        Updated user document
    """
    db = get_db()
    
    if category not in ["tourism", "restaurants", "hotels"]:
        raise ValueError("Invalid category. Must be tourism, restaurants, or hotels")
    
    # Create liked item document
    liked_item = {
        "item_id": item_id,
        "name": item_data.get("name"),
        "image_url": item_data.get("image_url"),
        "type": item_data.get("type"),
        "liked_at": datetime.utcnow()
    }
    
    # Check if item already liked
    user = db.users.find_one({
        "clerk_id": clerk_id,
        f"liked.{category}.item_id": item_id
    })
    
    if user:
        print(f"⚠️ Item {item_id} already liked by user {clerk_id}")
        return serialize_doc(user)
    
    # Add to liked list
    result = db.users.find_one_and_update(
        {"clerk_id": clerk_id},
        {
            "$push": {f"liked.{category}": liked_item},
            "$set": {"updated_at": datetime.utcnow()}
        },
        return_document=True
    )
    
    if result:
        print(f"💚 Item {item_id} added to {category} likes for user {clerk_id}")
        return serialize_doc(result)
    return None


def remove_liked_item(clerk_id: str, category: str, item_id: str) -> Optional[Dict]:
    """
    Remove an item from user's liked list
    
    Args:
        clerk_id: User's Clerk ID
        category: Category (tourism, restaurants, hotels)
        item_id: ID of the item to remove
    
    Returns:
        Updated user document
    """
    db = get_db()
    
    if category not in ["tourism", "restaurants", "hotels"]:
        raise ValueError("Invalid category. Must be tourism, restaurants, or hotels")
    
    result = db.users.find_one_and_update(
        {"clerk_id": clerk_id},
        {
            "$pull": {f"liked.{category}": {"item_id": item_id}},
            "$set": {"updated_at": datetime.utcnow()}
        },
        return_document=True
    )
    
    if result:
        print(f"💔 Item {item_id} removed from {category} likes for user {clerk_id}")
        return serialize_doc(result)
    return None


def get_user_liked_items(clerk_id: str, category: Optional[str] = None) -> Dict:
    """
    Get all liked items for a user
    
    Args:
        clerk_id: User's Clerk ID
        category: Optional category filter (tourism, restaurants, hotels)
    
    Returns:
        Dictionary with liked items
    """
    db = get_db()
    
    user = db.users.find_one({"clerk_id": clerk_id})
    
    if not user:
        return None
    
    liked_items = serialize_doc(user.get("liked", {}))
    
    if category:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise ValueError("Invalid category")
        return {category: liked_items.get(category, [])}
    
    return liked_items


def is_item_liked(clerk_id: str, category: str, item_id: str) -> bool:
    """
    Check if an item is liked by user
    
    Args:
        clerk_id: User's Clerk ID
        category: Category (tourism, restaurants, hotels)
        item_id: ID of the item
    
    Returns:
        True if liked, False otherwise
    """
    db = get_db()
    
    user = db.users.find_one({
        "clerk_id": clerk_id,
        f"liked.{category}.item_id": item_id
    })
    
    return user is not None


def get_user_stats(clerk_id: str) -> Optional[Dict]:
    """
    Get user statistics (liked counts, etc.)
    
    Args:
        clerk_id: User's Clerk ID
    
    Returns:
        Dictionary with user stats
    """
    db = get_db()
    
    user = db.users.find_one({"clerk_id": clerk_id})
    
    if not user:
        return None
    
    liked = user.get("liked", {})
    
    return {
        "clerk_id": clerk_id,
        "name": user.get("name"),
        "email": user.get("email"),
        "total_liked": sum([
            len(liked.get("tourism", [])),
            len(liked.get("restaurants", [])),
            len(liked.get("hotels", []))
        ]),
        "liked_counts": {
            "tourism": len(liked.get("tourism", [])),
            "restaurants": len(liked.get("restaurants", [])),
            "hotels": len(liked.get("hotels", []))
        },
        "member_since": user.get("created_at")
    }


def delete_user(clerk_id: str) -> bool:
    """
    Delete a user from the database
    
    Args:
        clerk_id: User's Clerk ID
    
    Returns:
        True if deleted, False if not found
    """
    db = get_db()
    
    result = db.users.delete_one({"clerk_id": clerk_id})
    
    if result.deleted_count > 0:
        print(f"🗑️ User deleted: {clerk_id}")
        return True
    return False