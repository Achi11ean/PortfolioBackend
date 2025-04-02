from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate  # Import Flask-Migrate
from sqlalchemy_serializer import SerializerMixin
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask_cors import CORS
from sqlalchemy import extract, func  # To filter by month
from dotenv import load_dotenv
import os
import requests

load_dotenv()


app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "*").split(",")}})
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
restricted_words = os.getenv("RESTRICTED_WORDS", "").split(",")
@app.route('/restricted_words', methods=['GET'])
def get_restricted_words():
    return jsonify(restricted_words) 
# Initialize Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db) 
# User model (for admin users)
# Before Request Hook
@app.before_request
def before_request():
    print(f"Incoming request to: {request.path} [{request.method}]")

    public_endpoints = {
        "/reviews/average": ["GET"],
        "/general_inquiries": ["GET", "POST", "PATCH", "DELETE"],
        "/engineering-bookings": ["POST", "PATCH", "DELETE", "GET"],
        "/total_expenses_and_mileage": ["POST", "PATCH", "DELETE", "GET"],
        "/mileage/<int:mileage_id>": ['PATCH'],
        "/income/<int:income_id>":["PATCH", "DELETE"],
        "/karaoke_hosting": ["POST", "PATCH", "DELETE", "GET"],
        "/income/aggregate": ["POST", "PATCH", "DELETE", "GET"],
        "/mileage": ["POST", "PATCH", "DELETE", "GET"],
        "/income": ["POST", "PATCH", "DELETE", "GET"],
        "/expenses": ["POST", "PATCH", "DELETE", "GET"],
        "/signup": ["POST"],
        "/login": ["POST"],
        "/reviews": ["GET", "POST"],
        "/bookings/monthly-earnings": ["GET"],
        "/bookings/search": ["GET"],
        "/gallery": ["GET", "POST", "DELETE"],
        "/contacts": ["POST","PATCH","DELETE", "GET"],
        "/api/bookings/dates": ["GET"],
        "/karaokesignup": ["POST", "PATCH", "GET", "DELETE"],
        "/formstate":["POST", "PATCH", "GET"],
        "/karaokesignup/<int:id>/move":["POST", "PATCH", "GET"],
        "/karaokesignup/deleted": ["GET"],
        "/djnotes":["POST", "PATCH", "GET", "DELETE"],
        "/djnotes/<int:id>":[ "PATCH", "GET", "DELETE"],
        "/djnotes/<int:id>/hard_delete": ["DELETE"],
        "/djnotes/deleted":["GET"],
        "/djnotesactive":["GET"],  
        "/karaokesignup/flagged":["GET"],
        "/karaokesignup/hard_delete": ["DELETE"],
        "/promotions":["POST", "PATCH", "GET", "DELETE"],
        "/promotions<int:id>":["POST", "PATCH", "GET", "DELETE"],
        "/karaokesignup/all":["GET"],
        "/restricted_words":["GET"],
        "/formstate": ["GET"], 
        "/formstate/set_pin": ["POST"], 
        "/formstate/update_pin": ["PATCH"],  
        "/formstate/delete_pin": ["DELETE"],  
        "/djnotes/reorder": ["PATCH"],
        "/karaokesignup/count":["GET"],
        "/music-break":["GET", "PATCH"],
        "/karaokesignup/singer_counts":["GET"],
        "/karaokesignup/active":["GET"],
        "/karaokesettings": ["GET","PATCH"],
        "/reviews/<int:id>/approve":["PATCH"],
        "/instagram-posts":["PATCH", "GET", "POST"],
        "/slider-images":["POST", "GET", "PATCH", "DELETE"],
        "/facebook-posts": ["GET"]

        


    }
    if request.method == 'OPTIONS':
        return  # Let CORS handle it

    for endpoint, methods in public_endpoints.items():
        if request.path.startswith(endpoint) and request.method in methods:
            print("Public endpoint, skipping token verification.")
            return

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is missing"}), 401
    
    try:
        token = token.split(" ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        current_user = User.query.filter_by(id=decoded_token['user_id']).first()

        if not current_user or not current_user.is_admin:
            return jsonify({"error": "Unauthorized access"}), 403
    except Exception as e:
        return jsonify({"error": "Invalid or expired token"}), 401

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Review model


# Review model (already defined)
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    service = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    website_url = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rating": self.rating,
            "service": self.service,
            "image_url": self.image_url,
            "website_url": self.website_url,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "is_approved": self.is_approved,
        }

# PATCH endpoint to update a review
@app.route("/reviews/<int:review_id>", methods=["PATCH"])
def update_review(review_id):
    review = Review.query.get_or_404(review_id)  # Fetch the review or return 404
    
    data = request.json  # Parse JSON request body

    # Update only the fields provided in the request
    if "name" in data:
        review.name = data["name"]
    if "rating" in data:
        review.rating = data["rating"]
    if "service" in data:
        review.service = data["service"]
    if "image_url" in data:
        review.image_url = data["image_url"]
    if "website_url" in data:
        review.website_url = data["website_url"]
    if "description" in data:
        review.description = data["description"]
    if "is_approved" in data:
        review.is_approved = data["is_approved"]

    # Commit the updated fields
    db.session.commit()

    return jsonify(review.to_dict()), 200  # Return the updated review



@app.route('/reviews/<int:id>/approve', methods=['PATCH'])
def approve_review(id):
    """
    Approve a review by setting is_approved to True.
    """
    print(f"Received PATCH request to approve review with ID: {id}")

    # Log request headers
    print("Request Headers:", request.headers)

    # Log request body (if any)
    try:
        request_data = request.json  # This will be None if there's no JSON body
        print("Request JSON Body:", request_data)
    except Exception as e:
        print("Error parsing JSON body:", e)
        request_data = None

    # Fetch the review
    review = Review.query.get(id)
    if not review:
        print(f"Review with ID {id} not found.")
        return jsonify({"error": "Review not found"}), 404

    # Log current review state
    print(f"Before update: Review ID: {review.id}, Approved: {review.is_approved}")

    # Approve the review
    review.is_approved = True
    db.session.commit()

    # Log new state
    print(f"After update: Review ID: {review.id}, Approved: {review.is_approved}")

    return jsonify({"message": "Review approved successfully!", "review": review.to_dict()}), 200




# Admin signup route
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    # Check if the username already exists
    existing_user = User.query.filter_by(username=data['username']).first()
    if existing_user:
        return jsonify({"error": "Username already exists"}), 400

    # Proceed to create the new user
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(
        username=data['username'],
        password=hashed_password,
        is_admin=data.get('is_admin', False)
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "Admin user created successfully"}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    print("Received login data:", data, flush=True)

    user = User.query.filter_by(username=data['username']).first()
    print("User found in DB:", user, flush=True)

    if not user:
        print("User not found", flush=True)
        return jsonify({"error": "Invalid username or password"}), 401

    print("Stored hashed password:", user.password, flush=True)
    print("Entered password:", data['password'], flush=True)

    if bcrypt.check_password_hash(user.password, data['password']):
        print("Password matched", flush=True)
        token = jwt.encode({
            'user_id': user.id,
            'is_admin': user.is_admin,  # Include is_admin field
            'exp': datetime.utcnow() + timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({"token": token, "is_admin": user.is_admin}), 200

    print("Password mismatch", flush=True)
    return jsonify({"error": "Invalid username or password"}), 401


@app.route('/reviews/<int:id>', methods=['DELETE'])
def delete_review(id):
    print(f"Attempting to delete review with ID: {id}")

    # Token verification is already handled in before_request
    review = Review.query.get(id)
    if review:
        db.session.delete(review)
        db.session.commit()
        return jsonify({"message": "Review deleted successfully"}), 200
    return jsonify({"error": "Review not found"}), 404



# Create a new review
@app.route('/reviews', methods=['POST'])
def create_review():
    """
    Create a new review with 'is_approved' set to False by default.
    """
    data = request.get_json()

    # Validate required fields
    if not all(key in data for key in ['name', 'rating', 'service', 'description']):
        return jsonify({"error": "Missing required fields: name, rating, service, description"}), 400

    try:
        # Create a new review instance with 'is_approved' as False
        new_review = Review(
            name=data['name'],
            rating=float(data['rating']),  # Ensures rating is a float
            service=data['service'],
            image_url=data.get('image_url'),  # Optional field
            website_url=data.get('website_url'),  # Optional field
            description=data['description'],
            is_approved=False  # Default to pending approval
        )

        # Add to database and commit
        db.session.add(new_review)
        db.session.commit()

        return jsonify({"message": "Review added and pending approval!", "review": new_review.to_dict()}), 201

    except ValueError:
        return jsonify({"error": "Invalid value for 'rating'. It must be a number (e.g., 4.5)."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/reviews/pending', methods=['GET'])
def get_pending_reviews():
    pending_reviews = Review.query.filter(Review.is_approved == False).all()
    print("Pending Reviews Query:", [r.to_dict() for r in pending_reviews])  # Debug log
    return jsonify([review.to_dict() for review in pending_reviews]), 200



@app.route('/reviews', methods=['GET'])
def get_reviews():
    search_term = request.args.get('service', '').strip()

    try:
        # Fetch only approved reviews
        query = Review.query.filter_by(is_approved=True)

        # Apply search filter if 'service' is provided
        if search_term:
            query = query.filter(Review.service.ilike(f"%{search_term}%"))

        reviews = query.all()  # ✅ Fetch reviews here first
        print("Fetched Reviews:", [r.to_dict() for r in reviews])  # ✅ Then debug here

        return jsonify([review.to_dict() for review in reviews]), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500






# Contact model
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(15), nullable=True)  # Optional
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Pending")  # New status field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "email": self.email,
            "message": self.message,
            "status": self.status,  # Include status
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

@app.route('/contacts', methods=['POST'])
def save_contact():
    print("---- Incoming POST Request to /contacts ----")  # Log incoming request
    data = request.get_json()
    print("Received Data:", data)  # Log the received data

    try:
        # Validate and log individual fields
        print("First Name:", data.get("first_Name"))
        print("Last Name:", data.get("last_Name"))
        print("Phone:", data.get("phone"))
        print("Email:", data.get("email"))
        print("Message:", data.get("message"))
        print("Status:", data.get("status", "Pending"))

        # Create new contact
        new_contact = Contact(
            first_name=data["first_Name"],
            last_name=data["last_Name"],
            phone=data.get('phone'),  # Optional
            email=data['email'],
            message=data['message'],
            status=data.get('status', "Pending"),  # Default to "Pending" if not provided
        )
        db.session.add(new_contact)
        db.session.commit()

        print("Contact saved successfully!")  # Confirm saving success
        return jsonify({"message": "Contact saved successfully!", "contact": new_contact.to_dict()}), 201


    except Exception as e:
        print("Error:", str(e))  # Log any other exceptions
        return jsonify({"error": str(e)}), 500

@app.route('/contacts', methods=['GET'])
def get_contacts():
    contacts = Contact.query.all()
    return jsonify([contact.to_dict() for contact in contacts]), 200

@app.route('/contacts/<int:id>', methods=['PATCH'])
def update_contact(id):
    data = request.get_json()
    contact = Contact.query.get(id)
    
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    # Update all fields if provided
    if "first_name" in data:
        contact.first_name = data["first_name"]
    if "last_name" in data:
        contact.last_name = data["last_name"]
    if "phone" in data:
        contact.phone = data["phone"]
    if "email" in data:
        contact.email = data["email"]
    if "message" in data:
        contact.message = data["message"]
    if "status" in data:
        contact.status = data["status"]
    db.session.commit()
    return jsonify({"message": "Contact updated successfully!", "contact": contact.to_dict()}), 200

# DELETE Contact Booking
@app.route('/contacts/<int:id>', methods=['DELETE'])
def delete_contact(id):
    contact = Contact.query.get(id)
    if not contact:
        return jsonify({"error": "Contact booking not found"}), 404
    
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": "Contact booking deleted successfully"}), 200
# Engineering Booking model
class EngineeringBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact = db.Column(db.String(120), nullable=False)  # Stores contact name
    contact_phone = db.Column(db.String(20), nullable=True)  # ✅ New field for phone
    project_name = db.Column(db.String(120), nullable=False)
    project_description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="Pending")
    notes = db.Column(db.Text, nullable=True)  # ✅ New field for additional notes
    date = db.Column(db.DateTime, nullable=True)  # ✅ NEW FIELD: Store the booking date
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "contact": self.contact,
            "contact_phone": self.contact_phone,
            "project_name": self.project_name,
            "project_description": self.project_description,
            "price": self.price,
            "status": self.status,
            "notes": self.notes,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,  # ✅ Convert date properly
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


@app.route('/engineering-bookings', methods=['POST'])
def save_engineering_booking():
    data = request.get_json()
    try:
        # ✅ Validate required fields before creating the instance
        if not data.get('contact_name') or not data.get('project_name'):
            return jsonify({"error": "Missing required fields: contact_name, project_name"}), 400

        # ✅ Parse date (ensure it is in a valid format)
        date_value = data.get('date')
        booking_date = None  # Default value if no date is provided

        if date_value:
            try:
                booking_date = datetime.strptime(date_value, "%Y-%m-%d")  # Ensure proper date format
            except ValueError:
                return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

        # ✅ Create a new EngineeringBooking instance
        new_booking = EngineeringBooking(
            contact=data['contact_name'],  # ✅ Updated field name
            contact_phone=data.get('contact_phone', ""),  # ✅ New field
            project_name=data['project_name'],
            project_description=data.get('project_description'),
            price=data.get('price'),
            status=data.get('status', "Pending"),
            notes=data.get('notes', ""),  # ✅ New field
            date=booking_date  # ✅ Save the parsed date
        )

        # ✅ Add to database and commit the transaction
        db.session.add(new_booking)
        db.session.commit()

        return jsonify({
            "message": "Booking saved successfully!",
            "booking": new_booking.to_dict()
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from datetime import datetime

@app.route('/engineering-bookings/<int:id>', methods=['PATCH'])
def update_engineering_booking(id):
    data = request.get_json()
    booking = EngineeringBooking.query.get(id)

    if not booking:
        return jsonify({"error": "Engineering booking not found"}), 404

    # ✅ Update fields if provided
    if "contact_name" in data:
        booking.contact = data["contact_name"]  # ✅ Updated field name
    if "contact_phone" in data:
        booking.contact_phone = data["contact_phone"]  # ✅ New field
    if "project_name" in data:
        booking.project_name = data["project_name"]
    if "project_description" in data:
        booking.project_description = data["project_description"]
    if "status" in data:
        booking.status = data["status"]
    if "price" in data:
        try:
            booking.price = float(data["price"])
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400
    if "notes" in data:
        booking.notes = data["notes"]  # ✅ New field

    # ✅ Handle `date` field update
    if "date" in data:
        date_value = data["date"]
        if date_value:
            try:
                booking.date = datetime.strptime(date_value, "%Y-%m-%d")  # Convert to proper format
            except ValueError:
                return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

    # ✅ Commit the changes
    db.session.commit()

    return jsonify({
        "message": "Booking updated successfully!",
        "booking": booking.to_dict()
    }), 200


# DELETE Engineering Booking
@app.route('/engineering-bookings/<int:id>', methods=['DELETE'])
def delete_engineering_booking(id):
    booking = EngineeringBooking.query.get(id)
    if not booking:
        return jsonify({"error": "Engineering booking not found"}), 404
    
    db.session.delete(booking)
    db.session.commit()
    return jsonify({"message": "Engineering booking deleted successfully"}), 200

@app.route('/engineering-bookings', methods=['GET'])
def get_engineering_bookings():
    try:
        bookings = EngineeringBooking.query.all()
        return jsonify([booking.to_dict() for booking in bookings]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


class GeneralInquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_name = db.Column(db.String(120), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=True)  # ✅ New phone field
    request = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, nullable=True)  # ✅ Change to DateTime
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,  # ✅ Include phone
            "request": self.request,
            "cost": self.cost,
            "notes": self.notes,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,  # ✅ Now properly formatted
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
from datetime import datetime

@app.route('/general_inquiries', methods=['POST'])
def create_general_inquiry():
    data = request.get_json()

    required_fields = ['contact_name', 'contact_phone', 'request', 'cost']  # ✅ Added contact_phone
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    try:
        # ✅ Convert date from string to DateTime (if provided)
        inquiry_date = None
        if 'date' in data and data['date']:
            try:
                inquiry_date = datetime.strptime(data['date'], "%Y-%m-%d")  # ✅ Ensure YYYY-MM-DD format
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        inquiry = GeneralInquiry(
            contact_name=data.get('contact_name'),
            contact_phone=data.get('contact_phone'),  
            request=data.get('request'),
            cost=data.get('cost'),
            notes=data.get('notes'),
            date=inquiry_date  # ✅ Store as DateTime
        )

        db.session.add(inquiry)
        db.session.commit()

        return jsonify({"message": "General inquiry created successfully!", "inquiry": inquiry.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/general_inquiries', methods=['GET'])
def get_general_inquiries():
    try:
        inquiries = GeneralInquiry.query.all()
        return jsonify([inquiry.to_dict() for inquiry in inquiries]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from datetime import datetime

@app.route('/general_inquiries/<int:inquiry_id>', methods=['PATCH'])
def update_general_inquiry(inquiry_id):
    data = request.get_json()
    inquiry = GeneralInquiry.query.get(inquiry_id)

    if not inquiry:
        return jsonify({"error": "General inquiry not found."}), 404

    try:
        if 'contact_name' in data:
            inquiry.contact_name = data['contact_name']
        if 'contact_phone' in data:  # ✅ Update phone field
            inquiry.contact_phone = data['contact_phone']
        if 'request' in data:
            inquiry.request = data['request']
        if 'cost' in data:
            inquiry.cost = data['cost']
        if 'notes' in data:
            inquiry.notes = data['notes']
        if 'date' in data:
            try:
                # ✅ Convert date string to datetime object
                inquiry.date = datetime.strptime(data['date'], "%Y-%m-%d")
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        db.session.commit()
        return jsonify({"message": "General inquiry updated successfully!", "inquiry": inquiry.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/general_inquiries/<int:inquiry_id>', methods=['DELETE'])
def delete_general_inquiry(inquiry_id):
    inquiry = GeneralInquiry.query.get(inquiry_id)

    if not inquiry:
        return jsonify({"error": "General inquiry not found."}), 404

    try:
        db.session.delete(inquiry)
        db.session.commit()
        return jsonify({"message": f"General inquiry with ID {inquiry_id} deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(120), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(50), nullable=False)  # Example: 'One-time', 'Monthly', 'Annually'
    purchase_date = db.Column(db.DateTime, nullable=False)
    purchase_location = db.Column(db.String(255), nullable=False)
    image_url_receipt = db.Column(db.String(255), nullable=True)  # Optional URL for the receipt image
    card_used = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "item": self.item,
            "cost": self.cost,
            "frequency": self.frequency,
            "purchase_date": self.purchase_date.strftime("%Y-%m-%d"),
            "purchase_location": self.purchase_location,
            "image_url_receipt": self.image_url_receipt,
            "card_used": self.card_used,
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


@app.route('/expenses', methods=['POST'])
def create_expense():
    data = request.get_json()

    required_fields = ['item', 'cost', 'frequency', 'purchase_date', 'purchase_location', 'card_used']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    try:
        expense = Expense(
            item=data.get('item'),
            cost=data.get('cost'),
            frequency=data.get('frequency'),
            purchase_date=datetime.strptime(data.get('purchase_date'), "%Y-%m-%d"),
            purchase_location=data.get('purchase_location'),
            image_url_receipt=data.get('image_url_receipt'),
            card_used=data.get('card_used'),
            notes=data.get('notes')
        )

        db.session.add(expense)
        db.session.commit()

        return jsonify({"message": "Expense created successfully!", "expense": expense.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/expenses', methods=['GET'])
def get_expenses():
    try:
        expenses = Expense.query.all()
        return jsonify([expense.to_dict() for expense in expenses]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    expense = Expense.query.get(expense_id)
    if not expense:
        return jsonify({"error": "Expense not found."}), 404

    return jsonify(expense.to_dict()), 200

@app.route('/expenses/<int:expense_id>', methods=['PATCH'])
def update_expense(expense_id):
    data = request.get_json()
    expense = Expense.query.get(expense_id)

    if not expense:
        return jsonify({"error": "Expense not found."}), 404

    try:
        if 'item' in data:
            expense.item = data['item']
        if 'cost' in data:
            expense.cost = data['cost']
        if 'frequency' in data:
            expense.frequency = data['frequency']
        if 'purchase_date' in data:
            expense.purchase_date = datetime.strptime(data['purchase_date'], "%Y-%m-%d")
        if 'purchase_location' in data:
            expense.purchase_location = data['purchase_location']
        if 'image_url_receipt' in data:
            expense.image_url_receipt = data['image_url_receipt']
        if 'card_used' in data:
            expense.card_used = data['card_used']
        if 'notes' in data:
            expense.notes = data['notes']

        db.session.commit()
        return jsonify({"message": "Expense updated successfully!", "expense": expense.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500



@app.route('/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    expense = Expense.query.get(expense_id)

    if not expense:
        return jsonify({"error": "Expense not found."}), 404

    try:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({"message": f"Expense with ID {expense_id} deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500




class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    income_name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    taxes = db.Column(db.Float, nullable=True)  # Optional field for taxes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "income_name": self.income_name,
            "amount": round(self.amount, 2),  # Ensuring proper decimal formatting
            "date": self.date.strftime("%Y-%m-%d"),
            "taxes": self.taxes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

@app.route('/income', methods=['POST'])
def create_income():
    data = request.get_json()
    
    # Debugging print statement
    print("Received POST request to /income with data:", data)

    required_fields = ['income_name', 'amount', 'date']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        print("Missing fields:", missing_fields)  # Debugging print
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    try:
        income = Income(
            income_name=data.get('income_name'),
            amount=data.get('amount'),
            date=datetime.strptime(data.get('date'), "%Y-%m-%d"),
            taxes=data.get('taxes')
        )

        db.session.add(income)
        db.session.commit()

        print("Income record successfully created:", income.to_dict())  # Debugging print
        return jsonify({"message": "Income record created successfully!", "income": income.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        print("Error creating income record:", str(e))  # Debugging print
        return jsonify({"error": str(e)}), 500


@app.route('/income', methods=['GET'])
def get_incomes():
    try:
        incomes = Income.query.all()
        return jsonify([income.to_dict() for income in incomes]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/income', methods=['PATCH'])
@app.route('/income/<int:income_id>', methods=['PATCH'])
def update_income(income_id=None):
    data = request.get_json()

    # If no income_id is provided, assign the next available ID
    if income_id is None:
        max_income = db.session.query(db.func.max(Income.id)).scalar()
        income_id = (max_income + 1) if max_income is not None else 1

    income = Income.query.get(income_id)

    if not income:
        # If the income record doesn't exist, create a new one
        try:
            new_income = Income(
                id=income_id,
                income_name=data.get('income_name', 'Unknown Income'),
                amount=data.get('amount', 0.0),
                date=datetime.strptime(data.get('date', datetime.today().strftime("%Y-%m-%d")), "%Y-%m-%d"),
                taxes=data.get('taxes', 0.0)
            )
            db.session.add(new_income)
            db.session.commit()
            return jsonify({"message": "New income record created!", "income": new_income.to_dict()}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    try:
        # Update existing income record
        if 'income_name' in data:
            income.income_name = data['income_name']
        if 'amount' in data:
            income.amount = data['amount']
        if 'date' in data:
            income.date = datetime.strptime(data['date'], "%Y-%m-%d")
        if 'taxes' in data:
            income.taxes = data['taxes']

        db.session.commit()
        return jsonify({"message": "Income record updated successfully!", "income": income.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/income/<int:income_id>', methods=['DELETE'])
def delete_income(income_id):
    print(f"Delete request received for income_id: {income_id}")  # Debugging
    income = Income.query.get(income_id)

    if not income:
        print("Income not found!")  # Debugging
        return jsonify({"error": "Income record not found."}), 404

    try:
        db.session.delete(income)
        db.session.commit()
        print(f"Deleted income_id: {income_id}")  # Debugging
        return jsonify({"message": f"Income record with ID {income_id} deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error: {str(e)}")  # Debugging
        return jsonify({"error": str(e)}), 500



@app.route('/income/aggregate', methods=['GET'])
def aggregate_income():
    try:
        # Fetch all manually added incomes
        manual_incomes = Income.query.all()
        
        # Fetch linked incomes from other tables
        engineering = EngineeringBooking.query.all()
        general_inquiries = GeneralInquiry.query.all()

        # Transform data into a unified structure
        income_list = []

        # Manually Added Incomes
        for inc in manual_incomes:
            income_list.append({
                "source": inc.income_name,  # Use income_name as the source
                "name": inc.income_name,    # Display name
                "amount": inc.amount,
                "date": inc.date.strftime("%Y-%m-%d"),
                "taxes": inc.taxes,
                "id": inc.id
            })

        # Engineering
        for eng in engineering:
            if eng.price:
                income_list.append({
                    "source": "Engineering Booking",
                    "name": f"{eng.contact} - {eng.project_name}",
                    "amount": eng.price,
                    "date": eng.date.strftime("%Y-%m-%d") if eng.date else None,  # Only use date field
                    "id": eng.id if eng.id else None  # Ensure an ID exists
                })

        # General Inquiries
        for gen in general_inquiries:
            if gen.cost:
                income_list.append({
                    "source": "General Inquiry",
                    "name": gen.contact_name,
                    "amount": gen.cost,
                    "date": gen.date.strftime("%Y-%m-%d") if gen.date else None,  # Only use date field
                    "id": gen.id if gen.id else None  # Ensure an ID exists
                })

        # Karaoke Hosting

        # Calculate total income
        total_income = sum(item['amount'] for item in income_list)

        return jsonify({"income_details": income_list, "total_income": total_income}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
HOME_ADDRESS = os.getenv("HOME_ADDRESS")

def get_distance_from_google(start, end):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": start,
        "destinations": end,
        "key": GOOGLE_MAPS_API_KEY,
        "units": "imperial"
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] != "OK":
        raise Exception("Google Maps API error: " + data.get("error_message", "Unknown error"))

    distance_text = data["rows"][0]["elements"][0]["distance"]["text"]  # e.g. "12.3 mi"
    distance_value = float(distance_text.replace("mi", "").strip())
    return distance_value


class MileageTracker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expense_name = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    start_location = db.Column(db.String(255), nullable=False)
    end_location = db.Column(db.String(255), nullable=False)
    distance_driven = db.Column(db.Float, nullable=False)  # One-way distance in miles
    is_round_trip = db.Column(db.Boolean, default=False, nullable=False)  # New field for round trip
    calculated_mileage = db.Column(db.Float, nullable=False)  # Auto-calculated at $0.67 per mile
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "expense_name": self.expense_name,
            "date": self.date.strftime("%Y-%m-%d"),
            "start_location": self.start_location,
            "end_location": self.end_location,
            "distance_driven": self.distance_driven,  # ✅ No extra adjustments
            "is_round_trip": self.is_round_trip,
            "calculated_mileage": round(self.distance_driven * 0.67, 2),  # ✅ Uses already adjusted distance
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

@app.route('/mileage', methods=['POST'])
def create_mileage():
    data = request.get_json()

    required_fields = ['expense_name', 'date', 'end_location']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    try:
        is_round_trip = data.get('is_round_trip', False)
        end_location = data['end_location']
        start_location = data.get('start_location')
        if not start_location or start_location.strip().lower() == "home":
            start_location = HOME_ADDRESS

        # 🗺️ Auto-calculate distance using Google Maps
        try:
            one_way_distance = get_distance_from_google(start_location, end_location)
        except Exception as api_error:
            print("❌ Google Maps API Error:", api_error)
            raise
        adjusted_distance = one_way_distance * (2 if is_round_trip else 1)
        calculated_mileage = round(adjusted_distance * 0.67, 2)

        mileage = MileageTracker(
            expense_name=data['expense_name'],
            date=datetime.strptime(data['date'], "%Y-%m-%d"),
            start_location=start_location,
            end_location=end_location,
            distance_driven=adjusted_distance,
            is_round_trip=is_round_trip,
            calculated_mileage=calculated_mileage,
            notes=data.get('notes')
        )

        db.session.add(mileage)
        db.session.commit()

        return jsonify({"message": "Mileage record created successfully!", "mileage": mileage.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/mileage/<int:mileage_id>', methods=['PATCH'])
def update_mileage(mileage_id):
    print(f"🔄 Incoming PATCH request for mileage ID: {mileage_id}")
    data = request.get_json()
    print(f"📩 Received data: {data}")

    mileage = MileageTracker.query.get(mileage_id)

    if not mileage:
        print("❌ Mileage record not found.")
        return jsonify({"error": "Mileage record not found."}), 404

    try:
        # ✅ Track previous state of is_round_trip
        previous_round_trip = mileage.is_round_trip

        # Update fields
        if 'expense_name' in data:
            print(f"📝 Updating expense_name: {data['expense_name']}")
            mileage.expense_name = data['expense_name']
        if 'date' in data:
            print(f"📅 Updating date: {data['date']}")
            mileage.date = datetime.strptime(data['date'], "%Y-%m-%d")
        if 'start_location' in data:
            print(f"📍 Updating start_location: {data['start_location']}")
            mileage.start_location = data['start_location']
        if 'end_location' in data:
            print(f"🏁 Updating end_location: {data['end_location']}")
            mileage.end_location = data['end_location']
        if 'distance_driven' in data:
            print(f"🛣️ Updating distance_driven: {data['distance_driven']}")
            mileage.distance_driven = data['distance_driven']
        if 'is_round_trip' in data:
            print(f"🔄 Updating is_round_trip: {data['is_round_trip']}")
            mileage.is_round_trip = data['is_round_trip']

            # ✅ Handle toggling of round trip selection
            if previous_round_trip and not mileage.is_round_trip:
                # Round trip deselected -> halve the distance
                print("🔄 Round trip deselected. Halving distance.")
                mileage.distance_driven /= 2
            elif not previous_round_trip and mileage.is_round_trip:
                # Round trip selected -> double the distance
                print("🔄 Round trip selected. Doubling distance.")
                mileage.distance_driven *= 2

        if 'notes' in data:
            print(f"🗒️ Updating notes: {data['notes']}")
            mileage.notes = data['notes']

        # ✅ Recalculate mileage reimbursement
        total_distance = mileage.distance_driven
        print(f"🧮 Calculated total_distance: {total_distance}")
        mileage.calculated_mileage = round(total_distance * 0.67, 2)
        print(f"💰 Recalculated mileage reimbursement: {mileage.calculated_mileage}")

        db.session.commit()
        print("✅ Mileage record updated successfully.")
        return jsonify({"message": "Mileage record updated successfully!", "mileage": mileage.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route('/mileage', methods=['GET'])
def get_mileages():
    try:
        mileages = MileageTracker.query.all()
        return jsonify([mileage.to_dict() for mileage in mileages]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/mileage/<int:mileage_id>', methods=['GET'])
def get_mileage(mileage_id):
    mileage = MileageTracker.query.get(mileage_id)
    if not mileage:
        return jsonify({"error": "Mileage record not found."}), 404

    return jsonify(mileage.to_dict()), 200


@app.route('/mileage/<int:mileage_id>', methods=['DELETE'])
def delete_mileage(mileage_id):
    mileage = MileageTracker.query.get(mileage_id)

    if not mileage:
        return jsonify({"error": "Mileage record not found."}), 404

    try:
        db.session.delete(mileage)
        db.session.commit()
        return jsonify({"message": f"Mileage record with ID {mileage_id} deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
@app.route('/total_expenses_and_mileage', methods=['GET'])
def get_total_expenses_and_mileage():
    try:
        # Calculate total expenses
        total_expenses = db.session.query(db.func.sum(Expense.cost)).scalar() or 0.0

        # Calculate total mileage reimbursement directly from the stored value
        total_mileage = db.session.query(db.func.sum(MileageTracker.calculated_mileage)).scalar() or 0.0

        # Calculate the combined total
        combined_total = round(total_expenses + total_mileage, 2)

        return jsonify({
            "total_expenses": round(total_expenses, 2),
            "total_mileage_reimbursement": round(total_mileage, 2),
            "combined_total": combined_total
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500





class KaraokeHosting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120), nullable=True)
    contact_phone = db.Column(db.String(20), nullable=True)  # ✅ Add this line

    location = db.Column(db.String(255), nullable=False)
    payment_amount = db.Column(db.Integer, nullable=False)
    frequency_date = db.Column(db.String(50), nullable=False)  # Could be 'Weekly', 'Monthly', or a specific date
    contract = db.Column(db.Text, nullable=True)  # Storing contract details or reference
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company_name": self.company_name,
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,  # ✅ Add this line
            "location": self.location,
            "payment_amount": self.payment_amount,
            "frequency_date": self.frequency_date,
            "contract": self.contract,
            "notes": self.notes,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

@app.route('/karaoke_hosting', methods=['POST'])
def create_karaoke_hosting():
    data = request.get_json()

    # Validate required fields
    required_fields = ['company_name', 'location', 'payment_amount', 'frequency_date']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    try:
        karaoke_hosting = KaraokeHosting(
            company_name=data.get('company_name'),
            contact_name=data.get('contact_name'),
            contact_phone=data.get('contact_phone'),  # ✅ Add this line
            location=data.get('location'),
            payment_amount=int(data.get('payment_amount', 0)),  # Ensure it's stored as an integer
            frequency_date=data.get('frequency_date'),
            contract=data.get('contract'),
            notes=data.get('notes')
        )

        db.session.add(karaoke_hosting)
        db.session.commit()

        return jsonify({"message": "Karaoke hosting event created successfully!", "karaoke_hosting": karaoke_hosting.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        print("Error details:", traceback.format_exc())  # Print the full stack trace
        return jsonify({"error": str(e)}), 500



@app.route('/karaoke_hosting/<int:k_id>', methods=['PATCH'])
def update_karaoke_hosting(k_id):
    data = request.get_json()
    karaoke_hosting = KaraokeHosting.query.get(k_id)

    if not karaoke_hosting:
        return jsonify({"error": "Karaoke hosting event not found."}), 404

    try:
        # Update fields if present in request
        if 'company_name' in data:
            karaoke_hosting.company_name = data['company_name']
        if 'contact_name' in data:
            karaoke_hosting.contact_name = data['contact_name']
        if 'location' in data:
            karaoke_hosting.location = data['location']
        if 'payment_amount' in data:
            karaoke_hosting.payment_amount = data['payment_amount']
        if 'frequency_date' in data:
            karaoke_hosting.frequency_date = data['frequency_date']
        if 'contract' in data:
            karaoke_hosting.contract = data['contract']
        if 'notes' in data:
            karaoke_hosting.notes = data['notes']

        db.session.commit()

        return jsonify({"message": "Karaoke hosting event updated successfully!", "karaoke_hosting": karaoke_hosting.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/karaoke_hosting/<int:k_id>', methods=['DELETE'])
def delete_karaoke_hosting(k_id):
    karaoke_hosting = KaraokeHosting.query.get(k_id)

    if not karaoke_hosting:
        return jsonify({"error": "Karaoke hosting event not found."}), 404

    try:
        db.session.delete(karaoke_hosting)
        db.session.commit()
        return jsonify({"message": f"Karaoke hosting event with ID {k_id} deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/karaoke_hosting', methods=['GET'])
def get_karaoke_hosting():
    try:
        karaoke_hostings = KaraokeHosting.query.all()
        return jsonify([event.to_dict() for event in karaoke_hostings]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500





VALID_PHOTO_TYPES = {"portrait", "couples", "Candid", "Group","events", "cosplay", "misc"}

class Gallery(db.Model):
    __tablename__ = "gallery"

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    photo_type = db.Column(db.String(20), nullable=False)  # Type: portrait, couples, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "caption": self.caption,
            "category": self.category,
            "photo_type": self.photo_type,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

def validate_photo_type(photo_type):
    """Validate that the photo type matches the allowed types."""
    if photo_type not in VALID_PHOTO_TYPES:
        raise ValueError(f"Invalid photo type. Allowed types: {', '.join(VALID_PHOTO_TYPES)}")

@app.route('/gallery', methods=['POST'])
def upload_photo():
    """
    Upload a new photo to the gallery.
    """
    data = request.get_json()

    # Extract required fields
    image_url = data.get("image_url")
    caption = data.get("caption", "")
    category = data.get("category", "Uncategorized")
    photo_type = data.get("photo_type", "").lower()

    # Validate photo type
    try:
        validate_photo_type(photo_type)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not image_url or not image_url.startswith(("http://", "https://")):
        return jsonify({"error": "Invalid or missing image URL."}), 400

    # Save to database
    new_photo = Gallery(
        image_url=image_url,
        caption=caption,
        category=category,
        photo_type=photo_type,
    )
    db.session.add(new_photo)
    db.session.commit()

    return jsonify({"message": "Photo added successfully!", "photo": new_photo.to_dict()}), 201


@app.route('/gallery', methods=['GET'])
def get_gallery():
    """
    Fetch all gallery photos with optional filters: category, photo_type.
    """
    category = request.args.get("category", "").strip()
    photo_type = request.args.get("photo_type", "").strip()

    query = Gallery.query

    if category:
        query = query.filter(Gallery.category.ilike(f"%{category}%"))
    if photo_type:
        query = query.filter(Gallery.photo_type.ilike(f"%{photo_type}%"))

    photos = query.all()
    return jsonify([photo.to_dict() for photo in photos]), 200


@app.route('/gallery/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    """
    Delete a photo from the gallery.
    """
    photo = Gallery.query.get(photo_id)
    if not photo:
        return jsonify({"error": "Photo not found"}), 404

    db.session.delete(photo)
    db.session.commit()
    return jsonify({"message": "Photo deleted successfully"}), 200


class Karaoke(db.Model):
    id = db.Column(db.Integer, primary_key=True)  
    name = db.Column(db.String(25), nullable=False)
    song = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now()) 
    is_flagged = db.Column(db.Boolean, default=False)  
    is_deleted = db.Column(db.Boolean, default=False)  # New soft delete flag
    position = db.Column(db.Integer, nullable=True)
    is_warning = db.Column(db.Boolean, default=False)  
    adjustment = db.Column(db.Float, nullable=True, default=0.0)



    def to_dict(self):
        """Convert the Karaoke entry into a dictionary."""
        data = {
            "id": self.id,
            "name": self.name,
            "song": self.song,
            "artist": self.artist,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_flagged": self.is_flagged,
            "is_deleted": self.is_deleted,  
            "position": self.position,
            "is_warning": self.is_warning, 
            "adjustment": self.adjustment 

        }
        print("Serialized Data Sent to Frontend:", data)  # ✅ Debugging log
        return data
@app.route("/karaokesignup/flagged", methods=["GET"])
def get_flagged_karaoke_signups():
    """Retrieve all flagged karaoke signups"""
    flagged_signups = Karaoke.query.filter_by(is_flagged=True, is_deleted=False).all()
    return jsonify([signup.to_dict() for signup in flagged_signups]), 200


@app.route("/karaokesignup", methods=["POST"])
def karaokesignup():
    data = request.get_json()
    if not data or not all(key in data for key in ["name", "song", "artist"]):
        return jsonify({"error": "Missing required fields"}), 400

    # Get the next available position
    max_position = db.session.query(db.func.max(Karaoke.position)).scalar()
    next_position = (max_position + 1) if max_position is not None else 1  # Start from 1 if empty
    adjustment = data.get("adjustment", 0.0)
    try:
        adjustment = float(adjustment)  # Ensure it's a valid float
    except ValueError:
        return jsonify({"error": "Invalid adjustment value. Must be a number."}), 400


    new_entry = Karaoke(
        name=data["name"],
        song=data["song"],
        artist=data["artist"],
        position=next_position,
        adjustment=adjustment
    )
    db.session.add(new_entry)
    db.session.commit()

    return jsonify(new_entry.to_dict()), 201

@app.route("/karaokesignup/<int:id>", methods=["PATCH"])
def update_karaoke_signup(id):
    print(f"🟡 Received PATCH request for ID: {id}")  # Log request ID

    data = request.get_json()
    print(f"🔍 Request JSON data: {data}")  # Log received JSON data

    entry = Karaoke.query.get(id)
    
    if not entry:
        print("❌ Signup not found!")  # Log missing entry
        return jsonify({"error": "Signup not found"}), 404

    print(f"🔄 BEFORE UPDATE → ID: {entry.id}, Name: {entry.name}, is_flagged: {entry.is_flagged}, Is warning: {entry.is_warning}")  

    # Track if any updates are made
    changes_made = False

    # Update only the provided fields
    if "name" in data and entry.name != data["name"]:
        print(f"✏️ Updating name: {entry.name} → {data['name']}")
        entry.name = data["name"]
        changes_made = True
    if "song" in data and entry.song != data["song"]:
        print(f"🎵 Updating song: {entry.song} → {data['song']}")
        entry.song = data["song"]
        changes_made = True
    if "artist" in data and entry.artist != data["artist"]:
        print(f"🎤 Updating artist: {entry.artist} → {data['artist']}")
        entry.artist = data["artist"]
        changes_made = True
    if "is_flagged" in data and entry.is_flagged != data["is_flagged"]:
        print(f"🚩 Updating is_flagged: {entry.is_flagged} → {data['is_flagged']}")
        entry.is_flagged = data["is_flagged"]
        changes_made = True
    if "is_warning" in data and entry.is_warning != data["is_warning"]:
        print(f"⚠️ Updating is_warning: {entry.is_warning} → {data['is_warning']}")
        entry.is_warning = data["is_warning"]
        changes_made = True
    if "adjustment" in data:
        try:
            new_adjustment = float(data["adjustment"])
            if entry.adjustment != new_adjustment:
                print(f"⚖️ Updating adjustment: {entry.adjustment} → {new_adjustment}")
                entry.adjustment = new_adjustment
                changes_made = True
        except ValueError:
            print("❌ Invalid adjustment value provided.")
            return jsonify({"error": "Invalid adjustment value. Must be a number."}), 400

    # Commit only if changes were made
    if changes_made:
        try:
            db.session.commit()
            print("✅ Database commit successful!")  

            # Fetch the updated entry
            updated_entry = Karaoke.query.get(id)
            print(f"🔍 AFTER COMMIT → ID: {updated_entry.id}, is_flagged: {updated_entry.is_flagged}")

            return jsonify(updated_entry.to_dict()), 200  # Return updated entry

        except Exception as e:
            db.session.rollback()
            print(f"❌ Database commit failed: {e}")  
            return jsonify({"error": "Database update failed"}), 500
    else:
        print("⚠️ No changes detected, returning current state.")
        return jsonify({"is_flagged": entry.is_flagged, "is_warning": entry.is_warning}), 200  # ✅ Return correct data even if no change


@app.route("/karaokesignup/count", methods=["GET"])
def get_active_karaoke_count():
    """Retrieve the number of active (not soft deleted) karaoke submissions for a specific singer."""
    singer_name = request.args.get("name", "").strip()

    if not singer_name:
        # Return total count if no specific name is provided
        active_count = Karaoke.query.filter(Karaoke.is_deleted == False).count()
        return jsonify({"active_count": active_count}), 200

    # Count active (non-deleted) signups for the specific singer
    active_singer_count = Karaoke.query.filter(
        Karaoke.name.ilike(singer_name), Karaoke.is_deleted == False
    ).count()

    return jsonify({"active_count": active_singer_count}), 200


@app.route("/karaokesignup/<int:id>", methods=["DELETE"])
def delete_karaoke_signup(id):
    entry = Karaoke.query.get(id)

    if not entry:
        return jsonify({"error": "Signup not found"}), 404

    db.session.delete(entry)
    db.session.commit()

    return jsonify({"message": "Signup deleted successfully"}), 200

@app.route("/karaokesignup", methods=["DELETE"])
def delete_all_karaoke_signups():
    try:
        num_deleted = db.session.query(Karaoke).delete()
        db.session.commit()
        return jsonify({"message": f"Deleted {num_deleted} signups successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
@app.route("/karaokesignup", methods=["GET"])
def get_all_karaoke_signups():
    search_term = request.args.get("search", "").strip().lower()

    query = Karaoke.query.filter_by(is_deleted=False)  # Don't fetch deleted entries

    if search_term:
        query = query.filter(
            (Karaoke.name.ilike(f"%{search_term}%")) | 
            (Karaoke.song.ilike(f"%{search_term}%")) | 
            (Karaoke.artist.ilike(f"%{search_term}%"))
        )  

    signups = query.order_by(Karaoke.position.asc()).all()
    
    # 🚀 Print EVERY signup to confirm is_flagged is being returned
    print("📡 Sending Karaoke Signups to Frontend:", [s.to_dict() for s in signups])

    return jsonify([signup.to_dict() for signup in signups]), 200



@app.route("/karaokesignup/<int:id>", methods=["GET"])
def get_karaoke_signup(id):
    signup = Karaoke.query.get(id)
    if not signup:
        return jsonify({"error": "Signup not found"}), 404
    return jsonify(signup.to_dict()), 200
@app.route("/karaokesignup/deleted", methods=["GET"])
def get_deleted_karaoke_signups():
    deleted_signups = Karaoke.query.filter_by(is_deleted=True).all()
    return jsonify([signup.to_dict() for signup in deleted_signups]), 200

@app.route("/karaokesignup/<int:id>/soft_delete", methods=["PATCH"])
def soft_delete_karaoke_signup(id):
    """Soft deletes a signup and updates positions"""
    entry = Karaoke.query.get(id)

    if not entry:
        return jsonify({"error": "Signup not found"}), 404

    # Mark entry as deleted
    entry.is_deleted = True
    db.session.query(Karaoke).filter_by(id=id).update({"is_deleted": True})
    db.session.commit()

    print(f"Signup {id} marked as deleted.")  # Debugging log

    # Re-fetch remaining signups that are NOT deleted
    signups = Karaoke.query.filter_by(is_deleted=False).order_by(Karaoke.position).all()

    # Recalculate positions (ensure no gaps in order)
    for i, signup in enumerate(signups):
        signup.position = i  # Update position sequentially
        db.session.query(Karaoke).filter_by(id=signup.id).update({"position": i})

    db.session.commit()  # ✅ Save updated positions

    return jsonify({"message": f"Signup {id} soft deleted and positions updated"}), 200

@app.route("/karaokesignup/active", methods=["GET"])
def get_active_karaoke_signups():
    """Retrieve all active (not soft deleted) karaoke signups."""
    active_signups = Karaoke.query.filter_by(is_deleted=False).all()
    return jsonify([signup.to_dict() for signup in active_signups]), 200


@app.route("/karaokesignup/<int:id>/move", methods=["PATCH"])
def move_karaoke_signup(id):
    print(f"Received request to move signup with ID: {id}")  # Debugging log

    data = request.json
    action = data.get("action")
    
    entry = Karaoke.query.get(id)
    if not entry:
        print(f"Signup with ID {id} not found")  # Debugging log
        return jsonify({"error": "Signup not found"}), 404

    # Fetch all signups ordered by position
    signups = Karaoke.query.filter_by(is_deleted=False).order_by(Karaoke.position).all()

    # Find current position index
    current_index = next((i for i, s in enumerate(signups) if s.id == id), None)
    
    if current_index is None:
        print(f"Signup with ID {id} not found in ordered list")  # Debugging log
        return jsonify({"error": "Signup not found in ordered list"}), 404
    
    print(f"Current index of ID {id}: {current_index}")  # Debugging log

    if action == "up":
        new_index = max(0, current_index - 1)
    elif action == "down":
        new_index = min(len(signups) - 1, current_index + 1)
    elif action == "up5":
        new_index = max(0, current_index - 5)
    elif action == "down5":
        new_index = min(len(signups) - 1, current_index + 5)
    elif action == "to_first":
        new_index = 0  # Move to first position
    elif action == "up_next":
        new_index = min(1, len(signups) - 1)  # Move to second position
    elif action == "sort_by_time":
        signups.sort(key=lambda x: x.created_at)  # Assuming a timestamp field exists
        for i, signup in enumerate(signups):
            signup.position = i
            db.session.query(Karaoke).filter_by(id=signup.id).update({"position": i})
        db.session.commit()
        return jsonify({"message": "Signups sorted by time"}), 200
    else:
        print(f"Invalid action received: {action}")  # Debugging log
        return jsonify({"error": "Invalid action"}), 400
    
    if new_index == current_index:
        print("No movement needed")  # Debugging log
        return jsonify({"message": "No movement needed"}), 200

    # ✅ Fix: Ensure safe list removal and reordering
    moving_entry = signups.pop(current_index)  # Remove the entry from the list

    if new_index == 0:  # Moving to the first position
        signups.insert(0, moving_entry)  # Insert at the beginning
    else:
        signups.insert(new_index, moving_entry)  # Insert at the correct position

    # ✅ Fix: Recalculate positions to prevent out-of-range errors
    for i, signup in enumerate(signups):
        signup.position = i
        db.session.query(Karaoke).filter_by(id=signup.id).update({"position": i})

    db.session.commit()
    
    return jsonify({"message": f"Signup moved {action}"}), 200



@app.route("/karaokesignup/sort", methods=["PATCH"])
def sort_karaoke_signups():
    print("Received request to sort signups by time.")  # Debugging log

    # Fetch all signups, sort by `created_at`
    signups = Karaoke.query.filter_by(is_deleted=False).order_by(Karaoke.created_at).all()

    # Update positions sequentially
    for i, signup in enumerate(signups):
        signup.position = i
        db.session.query(Karaoke).filter_by(id=signup.id).update({"position": i})

    db.session.commit()
    print("Signups successfully sorted by time.")  # Debugging log

    return jsonify({"message": "Signups sorted by time"}), 200



@app.route("/karaokesignup/singer_counts", methods=["GET"])
def get_singer_counts():
    """Retrieve the number of times each singer has performed throughout the entire night, including deleted entries, along with their songs."""
    results = (
        db.session.query(
            Karaoke.name, 
            func.count(Karaoke.id), 
            func.string_agg(Karaoke.song, ', ')
        )
        .group_by(Karaoke.name)
        .order_by(func.count(Karaoke.id).desc())  # Order by most performances
        .all()
    )

    # Format data into a structured JSON response
    singer_counts = [
        {"name": name, "count": count, "songs": songs.split(", ") if songs else []}  
        for name, count, songs in results
    ]

    return jsonify(singer_counts), 200



class FormState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    show_form = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())  
    pin_code = db.Column(db.String(4), nullable=True)  # 4-digit PIN stored as a string

    def to_dict(self):
        """Convert the FormState entry into a dictionary."""
        return {
            "id": self.id,
            "show_form": self.show_form,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "pin_code": self.pin_code,  # ✅ Include this to fix the issue

        }

# ============================
#   GET: Fetch form state
# ============================
@app.route("/formstate", methods=["GET"])
def get_form_state():
    """Retrieve the current form state, creating a default entry if none exists."""
    form_state = FormState.query.first()
    
    if not form_state:
        form_state = FormState(show_form=False)
        db.session.add(form_state)
        db.session.commit()

    return jsonify(form_state.to_dict()), 200

# ============================
#   POST: Set a New PIN
# ============================
@app.route("/formstate/set_pin", methods=["POST"])
def set_pin():
    data = request.get_json()
    new_pin = data.get("pin_code")

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"error": "PIN must be a 4-digit number"}), 400

    form_state = FormState.query.first()
    if not form_state:
        # 🚀 Default to opening signups when setting a new PIN
        form_state = FormState(pin_code=new_pin, show_form=True)  
        db.session.add(form_state)
    else:
        form_state.pin_code = new_pin
        form_state.show_form = True  # 🚀 Ensure signups open when setting a PIN

    db.session.commit()
    return jsonify({"message": "PIN set successfully, signups are now OPEN"}), 201

# ============================
#   PATCH: Update Existing PIN
# ============================
@app.route("/formstate/update_pin", methods=["PATCH"])
def update_pin():
    data = request.get_json()
    new_pin = data.get("pin_code")

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"error": "PIN must be a 4-digit number"}), 400

    form_state = FormState.query.first()
    if not form_state:
        return jsonify({"error": "No PIN found. Use POST to create one."}), 404

    form_state.pin_code = new_pin
    db.session.commit()
    
    return jsonify({"message": "PIN updated successfully"}), 200

# ============================
#   DELETE: Remove PIN
# ============================
@app.route("/formstate/delete_pin", methods=["DELETE"])
def delete_pin():
    form_state = FormState.query.first()
    if not form_state:
        return jsonify({"error": "No PIN found"}), 404

    form_state.pin_code = None
    form_state.show_form = False  # 👈 Hides form when PIN is deleted
    db.session.commit()

    return jsonify({"message": "PIN deleted successfully"}), 200


class DJNotes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50), nullable=False)  # Type of alert
    alert_details = db.Column(db.Text, nullable=False)  # Description/details of the alert
    created_at = db.Column(db.DateTime, default=db.func.now())  # Timestamp when alert is created
    is_active = db.Column(db.Boolean, default=True)  # Allows soft deletion or hiding alerts
    position = db.Column(db.Integer, nullable=False, default=0)  # NEW: Position for sorting

    def to_dict(self):
        """Convert DJ Notes entry into a dictionary."""
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "alert_details": self.alert_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
            "position": self.position,  # Include position in response

        }
@app.route("/djnotes", methods=["POST"])
def create_dj_note():
    data = request.get_json()

    # Validate required fields
    if not data or "alert_type" not in data or "alert_details" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    # Create new DJ Note
    new_note = DJNotes(
        alert_type=data["alert_type"],
        alert_details=data["alert_details"],
    )

    db.session.add(new_note)
    db.session.commit()

    return jsonify(new_note.to_dict()), 201

@app.route("/djnotes/<int:id>", methods=["PATCH"])
def update_dj_note(id):
    data = request.get_json()

    # Fetch the note by ID
    note = DJNotes.query.get(id)
    if not note:
        return jsonify({"error": "DJ Note not found"}), 404

    # Update only provided fields
    if "alert_type" in data:
        note.alert_type = data["alert_type"]
    if "alert_details" in data:
        note.alert_details = data["alert_details"]
    if "is_active" in data:
        note.is_active = data["is_active"]

    db.session.commit()
    
    return jsonify(note.to_dict()), 200

@app.route("/djnotesactive", methods=["GET"])
def get_all_dj_notes():
    notes = DJNotes.query.filter_by(is_active=True).order_by(DJNotes.position).all()
    return jsonify([note.to_dict() for note in notes]), 200


@app.route("/djnotes/deleted", methods=["GET"])
def get_deleted_dj_notes():
    deleted_notes = DJNotes.query.filter_by(is_active=False).order_by(DJNotes.created_at.desc()).all()
    return jsonify([note.to_dict() for note in deleted_notes]), 200


@app.route("/djnotesactive/<int:id>", methods=["GET"])
def get_dj_note(id):
    note = DJNotes.query.get(id)
    if not note:
        return jsonify({"error": "DJ Note not found"}), 404
    return jsonify(note.to_dict()), 200

@app.route("/djnotes/<int:id>", methods=["DELETE"])
def soft_delete_dj_note(id):
    note = DJNotes.query.get(id)
    if not note:
        return jsonify({"error": "DJ Note not found"}), 404

    note.is_active = False  # Soft delete
    db.session.commit()

    return jsonify({"message": f"DJ Note {id} has been soft deleted"}), 200

@app.route("/djnotes/<int:id>/hard_delete", methods=["DELETE"])
def hard_delete_dj_note(id):
    note = DJNotes.query.get(id)
    if not note:
        return jsonify({"error": "DJ Note not found"}), 404

    db.session.delete(note)  # Permanently delete
    db.session.commit()

    return jsonify({"message": f"DJ Note {id} has been permanently deleted"}), 200

@app.route("/djnotes/hard_delete_all", methods=["DELETE"])
def hard_delete_all_dj_notes():
    """Permanently delete all DJ Notes from the database."""
    try:
        num_deleted = DJNotes.query.delete()
        db.session.commit()
        return jsonify({"message": f"Successfully deleted {num_deleted} DJ Notes permanently."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete DJ Notes: {str(e)}"}), 500
@app.route("/karaokesignup/hard_delete", methods=["DELETE"])
def hard_delete_soft_deleted_karaoke_signups():
    """Permanently deletes only the signups that have been soft deleted"""
    try:
        # Delete entries where `is_deleted` is True
        num_deleted = Karaoke.query.filter_by(is_deleted=True).delete()
        db.session.commit()

        return jsonify({"message": f"Permanently deleted {num_deleted} soft-deleted signups"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
@app.route("/djnotes/reorder", methods=["PATCH"])
def reorder_dj_notes():
    """Move a specific alert to the top by updating its position."""
    try:
        data = request.get_json()
        if not data or "id" not in data:
            return jsonify({"error": "Missing note ID"}), 400

        note = DJNotes.query.get(data["id"])
        if not note:
            return jsonify({"error": "DJ Note not found"}), 404

        # Find the current alert at position 0
        current_top_note = DJNotes.query.filter_by(position=0).first()
        if current_top_note and current_top_note.id != note.id:
            current_top_note.position = db.session.query(db.func.max(DJNotes.position)).scalar() + 1  # Move it down

        # Move selected alert to position 0
        note.position = 0

        db.session.commit()  # ✅ Save both updates

        print(f"✅ Moved '{note.alert_type}' (ID {note.id}) to position 0")
        return jsonify({"message": "DJ Note moved to the top!", "id": note.id, "new_position": note.position}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to move DJ Note: {str(e)}"}), 500


    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to move DJ Note: {str(e)}"}), 500



class Promotions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # "performance" or "karaoke"
    event_date = db.Column(db.DateTime, nullable=False)  # Date and time of event
    location = db.Column(db.String(255), nullable=False)  # Where the event is happening
    image_url = db.Column(db.String(500), nullable=True)  # Optional: Photo reference
    description = db.Column(db.Text, nullable=False)  # Brief event description
    created_at = db.Column(db.DateTime, default=db.func.now())  # Timestamp when added

    def to_dict(self):
        """Convert the Promotions entry into a dictionary."""
        data = {
            "id": self.id,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "location": self.location,
            "image_url": self.image_url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        print("Serialized Data Sent to Frontend:", data)  # ✅ Debugging log
        return data

@app.route("/promotions", methods=["POST"])  # 🎯 Add "POST" explicitly!
def create_promotion():
    """Create a new promotion"""
    data = request.get_json()

    required_fields = ["event_type", "event_date", "location", "description"]
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        new_promotion = Promotions(
            event_type=data["event_type"],
            event_date=datetime.fromisoformat(data["event_date"]),
            location=data["location"],
            image_url=data.get("image_url"),  # Optional field
            description=data["description"]
        )
        db.session.add(new_promotion)
        db.session.commit()

        return jsonify(new_promotion.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    
@app.route("/promotions/<int:id>", methods=["PATCH"])
def update_promotion(id):
    """Update a promotion"""
    data = request.get_json()

    promotion = Promotions.query.get(id)
    if not promotion:
        return jsonify({"error": "Promotion not found"}), 404

    try:
        if "event_type" in data:
            promotion.event_type = data["event_type"]
        if "event_date" in data:
            promotion.event_date = datetime.fromisoformat(data["event_date"])
        if "location" in data:
            promotion.location = data["location"]
        if "image_url" in data:
            promotion.image_url = data["image_url"]
        if "description" in data:
            promotion.description = data["description"]

        db.session.commit()
        return jsonify(promotion.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route("/promotions", methods=["GET"])
def get_all_promotions():
    """Retrieve all promotions"""
    try:
        promotions = Promotions.query.all()
        return jsonify([promo.to_dict() for promo in promotions]), 200
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route("/promotions/<int:id>", methods=["GET"])
def get_promotion(id):
    """Retrieve a specific promotion by ID"""
    promotion = Promotions.query.get(id)
    
    if not promotion:
        return jsonify({"error": "Promotion not found"}), 404
    
    return jsonify(promotion.to_dict()), 200
@app.route("/promotions/<int:id>", methods=["DELETE"])
def delete_promotion(id):
    """Delete a specific promotion by ID"""
    promotion = Promotions.query.get(id)
    
    if not promotion:
        return jsonify({"error": "Promotion not found"}), 404

    try:
        db.session.delete(promotion)
        db.session.commit()
        return jsonify({"message": f"Promotion {id} deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route("/promotions", methods=["DELETE"])
def delete_all_promotions():
    """Delete ALL promotions (Hard Delete)"""
    try:
        num_deleted = db.session.query(Promotions).delete()
        db.session.commit()
        return jsonify({"message": f"Deleted {num_deleted} promotions successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route("/karaokesignup/all", methods=["GET"])
def get_all_signups():
    """Retrieve all karaoke signups, including soft-deleted ones"""
    try:
        signups = Karaoke.query.all()  # ✅ Fetch everything, including soft-deleted
        return jsonify([signup.to_dict() for signup in signups]), 200
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500




class MusicBreakState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    show_alert = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        """Convert the MusicBreakState entry into a dictionary."""
        return {
            "id": self.id,
            "show_alert": self.show_alert,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


@app.route("/music-break", methods=["GET"])
def get_music_break_state():
    state = MusicBreakState.query.first()
    if not state:
        # Create default state if none exists
        state = MusicBreakState()
        db.session.add(state)
        db.session.commit()
    
    return jsonify(state.to_dict()), 200

@app.route("/music-break", methods=["PATCH"])
def toggle_music_break():
    state = MusicBreakState.query.first()
    if not state:
        return jsonify({"error": "MusicBreakState not found"}), 404

    data = request.get_json()
    
    if "show_alert" in data:
        state.show_alert = data["show_alert"]  # Toggle based on request body
        state.last_updated = datetime.utcnow()
        db.session.commit()
        return jsonify(state.to_dict()), 200

    return jsonify({"error": "Invalid request"}), 400



class KaraokeSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    max_songs_per_singer = db.Column(db.Integer, default=1)  # Default to 1 song per singer

    def to_dict(self):
        return {
            "id": self.id,
            "max_songs_per_singer": self.max_songs_per_singer
        }

@app.route("/karaokesettings", methods=["GET"])
def get_karaoke_settings():
    settings = KaraokeSettings.query.first()
    if not settings:
        settings = KaraokeSettings(max_songs_per_singer=1)
        db.session.add(settings)
        db.session.commit()
    return jsonify(settings.to_dict()), 200

@app.route("/karaokesettings", methods=["PATCH"])
def update_karaoke_settings():
    data = request.get_json()
    settings = KaraokeSettings.query.first()
    if not settings:
        settings = KaraokeSettings()
        db.session.add(settings)
    
    if "max_songs_per_singer" in data:
        settings.max_songs_per_singer = data["max_songs_per_singer"]
    db.session.commit()
    return jsonify(settings.to_dict()), 200



class InstagramPosts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_urls = db.Column(db.Text, nullable=True)  # Comma-separated string
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "post_urls": self.post_urls,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

@app.route("/instagram-posts", methods=["GET"])
def get_instagram_posts():
    posts = InstagramPosts.query.first()
    if not posts:
        posts = InstagramPosts(post_urls="")
        db.session.add(posts)
        db.session.commit()
    return jsonify(posts.to_dict()), 200

@app.route("/instagram-posts", methods=["PATCH"])
def update_instagram_posts():
    data = request.get_json()
    post_urls = data.get("post_urls", "")
    posts = InstagramPosts.query.first()
    if not posts:
        posts = InstagramPosts(post_urls=post_urls)
        db.session.add(posts)
    else:
        posts.post_urls = post_urls
    db.session.commit()
    return jsonify(posts.to_dict()), 200

@app.route("/instagram-posts", methods=["DELETE"])
def delete_instagram_posts():
    posts = InstagramPosts.query.first()
    if not posts:
        return jsonify({"message": "No Instagram post data to delete."}), 200

    db.session.delete(posts)
    db.session.commit()
    return jsonify({"message": "Instagram post URLs deleted successfully."}), 200


@app.route("/instagram-posts/delete-one", methods=["PATCH"])
def delete_single_instagram_post():
    data = request.get_json()
    url_to_delete = data.get("url")

    if not url_to_delete:
        return jsonify({"error": "Missing URL to delete"}), 400

    posts = InstagramPosts.query.first()
    if not posts or not posts.post_urls:
        return jsonify({"message": "No posts available"}), 200

    # Remove matching URL
    urls = [url.strip() for url in posts.post_urls.split(",") if url.strip() != url_to_delete]
    posts.post_urls = ",".join(urls)

    db.session.commit()
    return jsonify({"message": "Post URL deleted successfully", "post_urls": posts.post_urls}), 200


class PhotoSliderImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat()
        }

@app.route("/slider-images/public", methods=["GET"])
def get_slider_images_public():
    images = PhotoSliderImage.query.order_by(PhotoSliderImage.created_at.desc()).all()
    return jsonify([img.to_dict() for img in images]), 200

@app.route("/slider-images", methods=["POST"])
def add_slider_image():
    data = request.get_json()
    image_url = data.get("image_url")
    if not image_url:
        return jsonify({"error": "Missing image URL"}), 400

    new_image = PhotoSliderImage(image_url=image_url)
    db.session.add(new_image)
    db.session.commit()

    return jsonify(new_image.to_dict()), 201


@app.route("/slider-images/<int:id>", methods=["DELETE"])
def delete_slider_image(id):
    image = PhotoSliderImage.query.get(id)
    if not image:
        return jsonify({"error": "Image not found"}), 404

    db.session.delete(image)
    db.session.commit()
    return jsonify({"message": "Image deleted"}), 200

@app.route("/facebook-posts")
def get_facebook_posts():
    access_token = os.getenv("FACEBOOK_TOKEN")
    url = f"https://graph.facebook.com/v19.0/441401162400735/posts"
    params = {
        "fields": "message,full_picture,created_time,permalink_url",
        "access_token": access_token
    }
    res = requests.get(url, params=params)
    return jsonify(res.json())


# Initialize database and run server
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
