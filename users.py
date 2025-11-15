"""
User management module for WanderEase
Handles user registration, profile management, and liked items
Fixed to handle URL-encoded clerk_ids
"""

from typing import Optional, Dict, List
from datetime import datetime
from urllib.parse import unquote
import db as database_module
from pymongo.errors import DuplicateKeyError

def get_db():
    """Get database instance"""
    return database_module.db

def serialize_doc(doc):
    """Use the serialize_doc function from db module"""
    return database_module.serialize_doc(doc)

def decode_clerk_id(clerk_id: str) -> str:
    """
    Decode URL-encoded clerk_id
    Handles cases like: 210acaioh%40iadia -> 210acaioh@iadia
    """
    decoded = unquote(clerk_id)
    print(f"🔑 Decoded clerk_id: '{clerk_id}' -> '{decoded}'")
    return decoded

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
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
    # Validate required fields
    if not clerk_id or not name or not email:
        raise ValueError("clerk_id, name, and email are required")
    
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
        result = db.users.insert_one(user_doc)
        print(f"✅ User created: {name} (clerk_id: {clerk_id}, MongoDB ID: {result.inserted_id})")
        
        # Return the created document
        user_doc.pop('_id', None)  # Remove MongoDB _id before returning
        return serialize_doc(user_doc)
    except DuplicateKeyError as e:
        print(f"⚠️ Duplicate key error for clerk_id: {clerk_id}")
        raise ValueError(f"User with clerk_id {clerk_id} already exists")
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        raise


def get_user_by_clerk_id(clerk_id: str) -> Optional[Dict]:
    """Get user by Clerk ID (handles URL-encoded IDs)"""
    db = get_db()
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
    user = db.users.find_one({"clerk_id": clerk_id})
    
    if user:
        print(f"✅ Found user: {clerk_id}")
    else:
        print(f"⚠️ User not found: {clerk_id}")
        
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
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
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
    
    print(f"⚠️ User not found for update: {clerk_id}")
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
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
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
        print(f"⚠️ Item {item_id} already liked by user {clerk_id} in category {category}")
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
        print(f"💚 Item '{liked_item.get('name', item_id)}' added to {category} likes for user {clerk_id}")
        return serialize_doc(result)
    
    print(f"⚠️ User not found when adding like: {clerk_id}")
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
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
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
    
    print(f"⚠️ User not found when removing like: {clerk_id}")
    return None


def get_user_liked_items(clerk_id: str, category: Optional[str] = None) -> Optional[Dict]:
    """
    Get all liked items for a user
    
    Args:
        clerk_id: User's Clerk ID
        category: Optional category filter (tourism, restaurants, hotels)
    
    Returns:
        Dictionary with liked items or None if user not found
    """
    db = get_db()
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
    user = db.users.find_one({"clerk_id": clerk_id})
    
    if not user:
        print(f"⚠️ User not found when fetching likes: {clerk_id}")
        return None
    
    liked_items = serialize_doc(user.get("liked", {}))
    
    if category:
        if category not in ["tourism", "restaurants", "hotels"]:
            raise ValueError("Invalid category")
        return {category: liked_items.get(category, [])}
    
    print(f"✅ Retrieved liked items for user: {clerk_id}")
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
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
    user = db.users.find_one({
        "clerk_id": clerk_id,
        f"liked.{category}.item_id": item_id
    })
    
    is_liked = user is not None
    print(f"🔍 Check if liked - User: {clerk_id}, Category: {category}, Item: {item_id} = {is_liked}")
    
    return is_liked


def get_user_stats(clerk_id: str) -> Optional[Dict]:
    """
    Get user statistics (liked counts, etc.)
    
    Args:
        clerk_id: User's Clerk ID
    
    Returns:
        Dictionary with user stats or None if user not found
    """
    db = get_db()
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
    user = db.users.find_one({"clerk_id": clerk_id})
    
    if not user:
        print(f"⚠️ User not found when fetching stats: {clerk_id}")
        return None
    
    liked = user.get("liked", {})
    
    stats = {
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
    
    print(f"✅ Retrieved stats for user: {clerk_id}")
    return stats


def delete_user(clerk_id: str) -> bool:
    """
    Delete a user from the database
    
    Args:
        clerk_id: User's Clerk ID
    
    Returns:
        True if deleted, False if not found
    """
    db = get_db()
    
    # Decode clerk_id in case it's URL-encoded
    clerk_id = decode_clerk_id(clerk_id)
    
    result = db.users.delete_one({"clerk_id": clerk_id})
    
    if result.deleted_count > 0:
        print(f"🗑️ User deleted: {clerk_id}")
        return True
    
    print(f"⚠️ User not found for deletion: {clerk_id}")
    return False