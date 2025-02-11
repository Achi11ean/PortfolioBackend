from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate  # Import Flask-Migrate
from sqlalchemy_serializer import SerializerMixin
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask_cors import CORS
from sqlalchemy import extract  # To filter by month
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize Flask app
# Initialize Flask app
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
        "/performance-bookings": ["POST", "GET", "PATCH"],
        "/engineering-bookings": ["POST", "GET"],
        "/signup": ["POST"],
        "/login": ["POST"],
        "/reviews": ["GET", "POST"],
        "/bookings/monthly-earnings": ["GET"],
        "/bookings/search": ["GET"],
        "/gallery": ["GET", "POST", "DELETE"],
        "/contacts": ["POST", "GET"],
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
        "/restricted_words":["GET"], "/formstate": ["GET"], 
        "/formstate/set_pin": ["POST"], 
        "/formstate/update_pin": ["PATCH"],  
        "/formstate/delete_pin": ["DELETE"],  

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
    review = Review.query.get(id)
    if not review:
        return jsonify({"error": "Review not found"}), 404

    review.is_approved = True
    db.session.commit()

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
    """
    Fetch approved reviews. Optional filter by service using query parameter.
    """
    search_term = request.args.get('service', '').strip()

    try:
        # Fetch only approved reviews
        query = Review.query.filter_by(is_approved=True)

        # Apply search filter if 'service' is provided
        if search_term:
            query = query.filter(Review.service.ilike(f"%{search_term}%"))

        reviews = query.all()
        return jsonify([review.to_dict() for review in reviews]), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/bookings/all', methods=['GET'])
def get_all_bookings():
    try:
        contacts = Contact.query.all()
        engineering_bookings = EngineeringBooking.query.all()
        performance_bookings = PerformanceBooking.query.all()

        results = {
            "contacts": [contact.to_dict() for contact in contacts],
            "engineering_bookings": [booking.to_dict() for booking in engineering_bookings],
            "performance_bookings": [booking.to_dict() for booking in performance_bookings]
        }

        return jsonify(results), 200
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
    price = db.Column(db.Float, nullable=True)  # Track earnings (optional)
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
            "price": self.price,  # Include price
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

@app.route('/contacts', methods=['POST'])
def save_contact():
    print("---- Incoming POST Request to /contacts ----")  # Log incoming request
    data = request.get_json()
    print("Received Data:", data)  # Log the received data

    try:
        # Validate and log individual fields
        print("First Name:", data.get("firstName"))
        print("Last Name:", data.get("lastName"))
        print("Phone:", data.get("phone"))
        print("Email:", data.get("email"))
        print("Message:", data.get("message"))
        print("Status:", data.get("status", "Pending"))
        print("Price:", data.get("price"))

        # Create new contact
        new_contact = Contact(
            first_name=data["firstName"],
            last_name=data["lastName"],
            phone=data.get('phone'),  # Optional
            email=data['email'],
            message=data['message'],
            status=data.get('status', "Pending"),  # Default to "Pending" if not provided
            price=float(data.get('price')) if data.get('price') else None  # Optional price field
        )
        db.session.add(new_contact)
        db.session.commit()

        print("Contact saved successfully!")  # Confirm saving success
        return jsonify({"message": "Contact saved successfully!", "contact": new_contact.to_dict()}), 201

    except ValueError as e:
        print("ValueError:", e)  # Log the ValueError
        return jsonify({"error": "Price must be a valid number"}), 400
    except Exception as e:
        print("Error:", str(e))  # Log any other exceptions
        return jsonify({"error": str(e)}), 500

@app.route('/contacts', methods=['GET'])
def get_contacts():
    contacts = Contact.query.all()
    return jsonify([contact.to_dict() for contact in contacts]), 200
@app.route('/engineering-bookings', methods=['GET'])
def get_engineering_bookings():
    engineering_bookings = EngineeringBooking.query.all()
    
    # Include contact data in the response
    result = []
    for booking in engineering_bookings:
        booking_dict = booking.to_dict()
        contact = Contact.query.get(booking.contact_id)
        if contact:
            booking_dict["contact"] = contact.to_dict()
        else:
            booking_dict["contact"] = None  # Handle missing contact
        result.append(booking_dict)
    
    return jsonify(result), 200

@app.route('/performance-bookings', methods=['GET'])
def get_performance_bookings():
    performance_bookings = PerformanceBooking.query.all()
    return jsonify([booking.to_dict() for booking in performance_bookings]), 200

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
    if "price" in data:
        try:
            contact.price = float(data["price"]) if data["price"] is not None else None
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400

    db.session.commit()
    return jsonify({"message": "Contact updated successfully!", "contact": contact.to_dict()}), 200



# Engineering Booking model
class EngineeringBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)  # Foreign key to Contact
    contact = db.relationship('Contact', backref='engineering_bookings')  # Establish relationship
    project_name = db.Column(db.String(120), nullable=False)
    project_type = db.Column(db.String(50), nullable=False)
    project_start_date = db.Column(db.String(50), nullable=False)
    project_end_date = db.Column(db.String(50), nullable=False)
    project_description = db.Column(db.Text, nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)  # Updated to Float
    status = db.Column(db.String(50), nullable=False, default="Pending")  # Status field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "contact": self.contact.to_dict(),  # Include contact details
            "project_name": self.project_name,
            "project_type": self.project_type,
            "project_start_date": self.project_start_date,
            "project_end_date": self.project_end_date,
            "project_description": self.project_description,
            "special_requests": self.special_requests,
            "price": self.price,
            "status": self.status,  # Include status
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
@app.route('/engineering-bookings', methods=['POST'])
def save_engineering_booking():
    data = request.get_json()
    try:
        # Retrieve the contact_id from the request data
        contact_id = data.get('contactId')
        if not contact_id:
            return jsonify({"error": "Contact ID is required"}), 400

        # Validate that the contact exists
        contact = Contact.query.get(contact_id)
        if not contact:
            return jsonify({"error": "Contact not found"}), 404

        # Create a new EngineeringBooking instance
        new_booking = EngineeringBooking(
            contact_id=contact_id,  # Associate the booking with the contact
            project_name=data['projectName'],
            project_type=data['projectType'],
            project_start_date=data['projectStartDate'],
            project_end_date=data['projectEndDate'],
            project_description=data.get('projectDescription'),
            special_requests=data.get('specialRequests'),
            price=data.get('price'),
            status=data.get('status', "Pending")  # Default to "Pending" if not provided
        )
        
        # Add to database and commit the transaction
        db.session.add(new_booking)
        db.session.commit()

        return jsonify({
            "message": "Booking saved successfully!",
            "booking": new_booking.to_dict()
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/engineering-bookings/<int:id>', methods=['PATCH'])
def update_engineering_booking(id):
    from datetime import datetime

    data = request.get_json()
    
    booking = EngineeringBooking.query.get(id)
    if not booking:
        return jsonify({"error": "Engineering booking not found"}), 404

    # Update fields
    if "project_name" in data:
        booking.project_name = data["project_name"]
    if "project_type" in data:
        booking.project_type = data["project_type"]

    if "project_start_date" in data:
        # Add default time of 10:00 AM if not already included
        date_str = data["project_start_date"]
        if "T" not in date_str:
            date_str += "T10:00:00"
        booking.project_start_date = date_str

    if "project_end_date" in data:
        # Add default time of 10:00 AM if not already included
        date_str = data["project_end_date"]
        if "T" not in date_str:
            date_str += "T10:00:00"
        booking.project_end_date = date_str

    if "project_description" in data:
        booking.project_description = data["project_description"]
    if "special_requests" in data:
        booking.special_requests = data["special_requests"]
    if "status" in data:
        booking.status = data["status"]
    if "price" in data:
        try:
            booking.price = float(data["price"])
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400

    # Commit the changes
    db.session.commit()

    # Return the full booking data
    return jsonify(booking.to_dict()), 200




@app.route('/bookings/monthly-earnings', methods=['GET'])
def get_monthly_earnings():
    try:
        def calculate_monthly_totals(model, price_column):
            # Query the total price for each month
            return [
                db.session.query(db.func.sum(price_column)).filter(
                    extract('month', model.created_at) == month,
                    model.status.in_(["Booked", "Booked & Paid", "Completed"])
                ).scalar() or 0  # Default to 0 if no results
                for month in range(1, 13)
            ]

        contact_monthly = calculate_monthly_totals(Contact, Contact.price)
        engineering_monthly = calculate_monthly_totals(EngineeringBooking, EngineeringBooking.price)
        performance_monthly = calculate_monthly_totals(PerformanceBooking, PerformanceBooking.price)

        return jsonify({
            "contact_monthly": contact_monthly,
            "engineering_monthly": engineering_monthly,
            "performance_monthly": performance_monthly
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Performance Booking model
class PerformanceBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)  # Foreign key to Contact
    contact = db.relationship('Contact', backref='performance_bookings')  # Establish relationship
    event_name = db.Column(db.String(120), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    event_date_time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    guests = db.Column(db.String(10), nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)  # Updated to Float
    status = db.Column(db.String(50), nullable=False, default="Pending")  # Status field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "contact": self.contact.to_dict(),  # Include contact details
            "event_name": self.event_name,
            "event_type": self.event_type,
            "event_date_time": self.event_date_time,
            "location": self.location,
            "guests": self.guests,
            "special_requests": self.special_requests,
            "price": self.price,
            "status": self.status,  # Include status
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

@app.route('/performance-bookings', methods=['POST'])
def save_performance_booking():
    data = request.get_json()
    try:
        # Fetch the contact using contact_id from the request
        contact = Contact.query.get(data.get('contactId'))
        if not contact:
            return jsonify({"error": "Contact not found"}), 404

        # Create a new PerformanceBooking with the associated contact
        new_booking = PerformanceBooking(
            contact_id=contact.id,  # Associate with the Contact
            event_name=data['eventName'],
            event_type=data['eventType'],
            event_date_time=data['eventDateTime'],
            location=data['location'],
            guests=data.get('guests'),
            special_requests=data.get('specialRequests'),
            price=data.get('price'),  # Renamed field
            status=data.get('status', "Pending")  # Default status if not provided
        )
        db.session.add(new_booking)
        db.session.commit()

        return jsonify({
            "message": "Performance booking saved successfully!",
            "booking": new_booking.to_dict()
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/performance-bookings/<int:id>', methods=['PATCH'])
def update_performance_booking(id):
    from datetime import datetime

    data = request.get_json()
    booking = PerformanceBooking.query.get(id)
    
    if not booking:
        return jsonify({"error": "Performance booking not found"}), 404

    # Update fields
    if "contactId" in data:
        contact = Contact.query.get(data["contactId"])
        if not contact:
            return jsonify({"error": "Contact not found"}), 404
        booking.contact_id = contact.id  # Associate the booking with the contact

    if "eventName" in data:
        booking.event_name = data["eventName"]

    if "eventType" in data:
        booking.event_type = data["eventType"]

    if "eventDateTime" in data:
        # Add default time of 10:00 AM if not already included
        date_str = data["eventDateTime"]
        if "T" not in date_str:
            date_str += "T10:00:00"
        booking.event_date_time = date_str

    if "location" in data:
        booking.location = data["location"]

    if "guests" in data:
        booking.guests = data["guests"]

    if "specialRequests" in data:
        booking.special_requests = data["specialRequests"]

    if "price" in data:
        try:
            booking.price = float(data["price"])  # Ensure price is stored as a float
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400

    if "status" in data:
        booking.status = data["status"]

    # Commit the changes
    db.session.commit()

    # Return the updated booking
    return jsonify({"message": "Performance booking updated successfully!", "booking": booking.to_dict()}), 200




@app.route('/reviews/average', methods=['GET'])
def get_average_review():
    try:
        # Calculate the average rating
        average_rating = db.session.query(db.func.avg(Review.rating)).scalar()

        if average_rating is None:
            return jsonify({"message": "No reviews available to calculate average."}), 404

        return jsonify({
            "average_rating": round(average_rating, 2)  # Round to 2 decimal places
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/bookings/booked', methods=['GET'])
def get_booked_entries():
    try:
        contacts = Contact.query.filter(Contact.status.in_(["Booked", "Booked & Paid"])).all()
        engineering_bookings = EngineeringBooking.query.filter(EngineeringBooking.status.in_(["Booked", "Booked & Paid"])).all()
        performance_bookings = PerformanceBooking.query.filter(PerformanceBooking.status.in_(["Booked", "Booked & Paid"])).all()

        results = {
            "contacts": [contact.to_dict() for contact in contacts],
            "engineering_bookings": [booking.to_dict() for booking in engineering_bookings],
            "performance_bookings": [booking.to_dict() for booking in performance_bookings]
        }

        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/bookings/search', methods=['GET'])
def search_bookings():
    """
    Search bookings across Contact, EngineeringBooking, and PerformanceBooking tables.
    Filters by name, phone number, and status type (case-insensitive).
    """
    try:
        # Extract query parameters
        name_query = request.args.get('name', '').strip().lower()
        phone_query = request.args.get('phone', '').strip()
        status_query = request.args.get('status', '').strip().lower()

        # Base query for each model
        contacts_query = Contact.query
        engineering_query = EngineeringBooking.query
        performance_query = PerformanceBooking.query

        # Apply name filters if provided
        if name_query:
            contacts_query = contacts_query.filter(
                db.or_(
                    db.func.lower(Contact.first_name).like(f"%{name_query}%"),
                    db.func.lower(Contact.last_name).like(f"%{name_query}%")
                )
            )
            engineering_query = engineering_query.filter(
                db.func.lower(EngineeringBooking.client_name).like(f"%{name_query}%")
            )
            performance_query = performance_query.filter(
                db.func.lower(PerformanceBooking.client_name).like(f"%{name_query}%")
            )

        # Apply phone filters if provided
        if phone_query:
            contacts_query = contacts_query.filter(Contact.phone.like(f"%{phone_query}%"))
            engineering_query = engineering_query.filter(EngineeringBooking.client_phone.like(f"%{phone_query}%"))
            performance_query = performance_query.filter(PerformanceBooking.client_phone.like(f"%{phone_query}%"))

        # Apply status filters if provided
        if status_query:
            contacts_query = contacts_query.filter(
                db.func.lower(Contact.status).like(f"%{status_query}%")
            )
            engineering_query = engineering_query.filter(
                db.func.lower(EngineeringBooking.status).like(f"%{status_query}%")
            )
            performance_query = performance_query.filter(
                db.func.lower(PerformanceBooking.status).like(f"%{status_query}%")
            )

        # Execute the queries
        contacts = contacts_query.all()
        engineering_bookings = engineering_query.all()
        performance_bookings = performance_query.all()

        # Combine results
        results = {
            "contacts": [contact.to_dict() for contact in contacts],
            "engineering_bookings": [booking.to_dict() for booking in engineering_bookings],
            "performance_bookings": [booking.to_dict() for booking in performance_bookings]
        }

        return jsonify(results), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# DELETE Contact Booking
@app.route('/contacts/<int:id>', methods=['DELETE'])
def delete_contact(id):
    contact = Contact.query.get(id)
    if not contact:
        return jsonify({"error": "Contact booking not found"}), 404
    
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"message": "Contact booking deleted successfully"}), 200

# DELETE Engineering Booking
@app.route('/engineering-bookings/<int:id>', methods=['DELETE'])
def delete_engineering_booking(id):
    booking = EngineeringBooking.query.get(id)
    if not booking:
        return jsonify({"error": "Engineering booking not found"}), 404
    
    db.session.delete(booking)
    db.session.commit()
    return jsonify({"message": "Engineering booking deleted successfully"}), 200

# DELETE Performance Booking
@app.route('/performance-bookings/<int:id>', methods=['DELETE'])
def delete_performance_booking(id):
    booking = PerformanceBooking.query.get(id)
    if not booking:
        return jsonify({"error": "Performance booking not found"}), 404
    
    db.session.delete(booking)
    db.session.commit()
    return jsonify({"message": "Performance booking deleted successfully"}), 200


@app.route('/bookings/total-earnings', methods=['GET'])
def get_total_earnings():
    try:
        # Sum up prices for "Booked", "Booked & Paid", and "Completed" statuses in each table
        contact_total = db.session.query(db.func.sum(Contact.price)).filter(
            Contact.status.in_(["Booked", "Booked & Paid", "Completed"])
        ).scalar() or 0  # Default to 0 if None
        
        engineering_total = db.session.query(db.func.sum(EngineeringBooking.price)).filter(
            EngineeringBooking.status.in_(["Booked", "Booked & Paid", "Completed"])
        ).scalar() or 0
        
        performance_total = db.session.query(db.func.sum(PerformanceBooking.price)).filter(
            PerformanceBooking.status.in_(["Booked", "Booked & Paid", "Completed"])
        ).scalar() or 0


        # Calculate the grand total
        grand_total = contact_total + float(engineering_total) + float(performance_total)

        return jsonify({
            "contact_total": round(contact_total, 2),
            "engineering_total": round(float(engineering_total), 2),
            "performance_total": round(float(performance_total), 2),
            "grand_total": round(grand_total, 2)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/bookings/potential-earnings', methods=['GET'])
def get_paid_completed_earnings():
    try:
        # Sum up prices for "Booked & Paid" and "Completed" statuses in each table
        contact_total = db.session.query(db.func.sum(Contact.price)).filter(
            Contact.status.in_(["Booked & Paid", "Completed"])
        ).scalar() or 0  # Default to 0 if None
        
        engineering_total = db.session.query(db.func.sum(EngineeringBooking.price)).filter(
            EngineeringBooking.status.in_(["Booked & Paid", "Completed"])
        ).scalar() or 0
        
        performance_total = db.session.query(db.func.sum(PerformanceBooking.price_range)).filter(
            PerformanceBooking.status.in_(["Booked & Paid", "Completed"])
        ).scalar() or 0

        # Calculate the grand total
        grand_total = contact_total + float(engineering_total) + float(performance_total)

        return jsonify({
            "contact_total": round(contact_total, 2),
            "engineering_total": round(float(engineering_total), 2),
            "performance_total": round(float(performance_total), 2),
            "grand_total": round(grand_total, 2)
        }), 200

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


@app.route('/api/bookings/dates', methods=['GET'])
def get_booking_dates():
    try:
        def parse_date(date_value):
            if isinstance(date_value, str):
                try:
                    return datetime.fromisoformat(date_value)
                except ValueError:
                    return None
            return date_value

        # Fetch EngineeringBooking dates
        engineering_bookings = EngineeringBooking.query.all()
        engineering_dates = [
            {
                "id": booking.id,
                "type": "Engineering",
                "title": booking.project_name,
                "start": parse_date(booking.project_start_date).isoformat() if parse_date(booking.project_start_date) else None,
                "end": parse_date(booking.project_end_date).isoformat() if parse_date(booking.project_end_date) else None,
                "status": booking.status,
                "description": booking.project_description or "No description available",
                "contact": booking.contact.to_dict() if booking.contact else None,
            }
            for booking in engineering_bookings
        ]

        # Fetch PerformanceBooking dates
        performance_bookings = PerformanceBooking.query.all()
        performance_dates = [
            {
                "id": booking.id,
                "type": "Performance",
                "title": booking.event_name,
                "start": parse_date(booking.event_date_time).isoformat() if parse_date(booking.event_date_time) else None,
                "end": parse_date(booking.event_date_time).isoformat() if parse_date(booking.event_date_time) else None,
                "status": booking.status,
                "description": booking.special_requests or "No special requests",
                "contact": booking.contact.to_dict() if booking.contact else None,
            }
            for booking in performance_bookings
        ]

        all_dates = engineering_dates + performance_dates
        return jsonify(all_dates), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

class Karaoke(db.Model):
    id = db.Column(db.Integer, primary_key=True)  
    name = db.Column(db.String(25), nullable=False)
    song = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now()) 
    is_flagged = db.Column(db.Boolean, default=False)  
    is_deleted = db.Column(db.Boolean, default=False)  # New soft delete flag
    position = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        """Convert the Karaoke entry into a dictionary."""
        data = {
            "id": self.id,
            "name": self.name,
            "song": self.song,
            "artist": self.artist,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_flagged": self.is_flagged,
            "is_deleted": self.is_deleted,  # Include soft delete flag
            "position": self.position
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

    new_entry = Karaoke(
        name=data["name"],
        song=data["song"],
        artist=data["artist"],
        position=next_position  # Assign a valid position
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

    print(f"🔄 BEFORE UPDATE → ID: {entry.id}, Name: {entry.name}, is_flagged: {entry.is_flagged}")  

    # Update only the provided fields
    if "name" in data:
        print(f"✏️ Updating name: {entry.name} → {data['name']}")
        entry.name = data["name"]
    if "song" in data:
        print(f"🎵 Updating song: {entry.song} → {data['song']}")
        entry.song = data["song"]
    if "artist" in data:
        print(f"🎤 Updating artist: {entry.artist} → {data['artist']}")
        entry.artist = data["artist"]
    if "is_flagged" in data:
        print(f"🚩 Updating is_flagged: {entry.is_flagged} → {data['is_flagged']}")
        entry.is_flagged = data["is_flagged"]

    try:
        db.session.commit()
        print("✅ Database commit successful!")  

        # 🔥 FETCH FROM DATABASE AGAIN TO CHECK IF IT REALLY SAVED
        updated_entry = Karaoke.query.get(id)
        print(f"🔍 AFTER COMMIT → ID: {updated_entry.id}, is_flagged: {updated_entry.is_flagged}")

        return jsonify(updated_entry.to_dict()), 200  # Return updated entry

    except Exception as e:
        db.session.rollback()
        print(f"❌ Database commit failed: {e}")  
        return jsonify({"error": "Database update failed"}), 500


    updated_entry = entry.to_dict()
    print(f"Updated entry: {updated_entry}")  # Log final updated entry

    return jsonify(updated_entry), 200


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
        form_state = FormState(pin_code=new_pin, show_form=False)
        db.session.add(form_state)
    else:
        form_state.pin_code = new_pin
        form_state.show_form = False  # Reset visibility when setting a new PIN

    db.session.commit()
    return jsonify({"message": "PIN set successfully"}), 201

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
    form_state.show_form = False  # Hide form when PIN is deleted
    db.session.commit()

    return jsonify({"message": "PIN deleted successfully"}), 200

class DJNotes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50), nullable=False)  # Type of alert
    alert_details = db.Column(db.Text, nullable=False)  # Description/details of the alert
    created_at = db.Column(db.DateTime, default=db.func.now())  # Timestamp when alert is created
    is_active = db.Column(db.Boolean, default=True)  # Allows soft deletion or hiding alerts

    def to_dict(self):
        """Convert DJ Notes entry into a dictionary."""
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "alert_details": self.alert_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
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
    notes = DJNotes.query.filter_by(is_active=True).order_by(DJNotes.created_at.desc()).all()
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


# Initialize database and run server
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
