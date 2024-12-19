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

# Initialize Flask app
# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5174"}})
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reviews.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Change to a secure key in production

# Initialize Extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db) 
# User model (for admin users)
# Before Request Hook
@app.before_request
def before_request():
    """
    Logs the endpoint being accessed and ensures certain routes are public.
    """
    print(f"Incoming request to: {request.path} [{request.method}]")

    # Define public routes explicitly with method checks
    public_endpoints = {
        "/reviews/average": ["GET"],
        "/performance-bookings": ["POST", "GET"],
        "/engineering-bookings": ["POST", "GET"],
        "/signup": ["POST"],
        "/login": ["POST"],
        "/reviews": ["GET", "POST"],
        "/bookings/monthly-earnings": ["GET"],
        "/bookings/search": ["GET"],  # Mark the search endpoint as public


        
    }

    # Allow specific endpoints
    if request.path in public_endpoints and request.method in public_endpoints[request.path]:
        print("Public endpoint, skipping token verification.")
        return  # Skip token checks for public routes

    if request.path.startswith("/reviews/") and request.method == "GET":
        print("Public GET request to reviews, skipping token verification.")
        return

    if request.method == "OPTIONS":
        print("CORS preflight request allowed.")
        return  # Allow CORS preflight requests

    # Protect all other routes
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({"error": "Token is missing"}), 401
    
    try:
        # Extract token after "Bearer"
        token = token.split(" ")[1]
        print(f"Received Token: {token}", flush=True)

        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        print(f"Decoded Token: {decoded_token}", flush=True)

        current_user = User.query.filter_by(id=decoded_token['user_id']).first()
        print(f"User: {current_user}", flush=True)

        if not current_user or not current_user.is_admin:
            return jsonify({"error": "Unauthorized access"}), 403

    except IndexError:
        return jsonify({"error": "Token format invalid. Use 'Bearer <token>'"}), 401
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError as e:
        print(f"Invalid Token: {e}", flush=True)
        return jsonify({"error": "Invalid token"}), 401




class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Review model
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Float, nullable=False)  # Allows ratings like 4.5
    service = db.Column(db.String(50), nullable=False)  # Dropdown values (e.g., karaoke, software engineering)
    image_url = db.Column(db.String(255), nullable=True)  # Optional field for image URL
    website_url = db.Column(db.String(255), nullable=True)  # Optional field for website URL
    description = db.Column(db.Text, nullable=False)  # Description field for additional details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rating": self.rating,
            "service": self.service,
            "image_url": self.image_url,
            "website_url": self.website_url,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }


# Helper function to protect routes
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        print(f"Token received: {token}", flush=True)

        if not token:
            return jsonify({"error": "Token is missing"}), 401
        try:
            decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=decoded_token['user_id']).first()
            if not current_user or not current_user.is_admin:
                return jsonify({"error": "Unauthorized access"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated

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
    data = request.get_json()

    # Validate required fields
    if not all(key in data for key in ['name', 'rating', 'service', 'description']):
        return jsonify({"error": "Missing required fields: name, rating, service, description"}), 400

    try:
        # Create a new review instance
        new_review = Review(
            name=data['name'],
            rating=float(data['rating']),  # Ensures rating is a float
            service=data['service'],
            image_url=data.get('image_url'),  # Optional field
            website_url=data.get('website_url'),  # Optional field
            description=data['description']
        )

        # Add to database and commit
        db.session.add(new_review)
        db.session.commit()

        return jsonify({"message": "Review added!", "review": new_review.to_dict()}), 201

    except ValueError:
        return jsonify({"error": "Invalid value for 'rating'. It must be a number (e.g., 4.5)."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reviews', methods=['GET'])
def get_reviews():
    # Get the search term from query parameters
    search_term = request.args.get('service', '').strip()

    try:
        if search_term:
            reviews = Review.query.filter(Review.service.ilike(f"%{search_term}%")).all()
        else:
            reviews = Review.query.all()

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
    data = request.get_json()
    try:
        new_contact = Contact(
            first_name=data['firstName'],
            last_name=data['lastName'],
            phone=data.get('phone'),  # Optional
            email=data['email'],
            message=data['message'],
            status=data.get('status', "Pending"),  # Default to "Pending" if not provided
            price=float(data.get('price')) if data.get('price') else None  # Optional price field
        )
        db.session.add(new_contact)
        db.session.commit()
        return jsonify({"message": "Contact saved successfully!", "contact": new_contact.to_dict()}), 201
    except ValueError:
        return jsonify({"error": "Price must be a valid number"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/contacts', methods=['GET'])
def get_contacts():
    contacts = Contact.query.all()
    return jsonify([contact.to_dict() for contact in contacts]), 200
@app.route('/engineering-bookings', methods=['GET'])
def get_engineering_bookings():
    engineering_bookings = EngineeringBooking.query.all()
    return jsonify([booking.to_dict() for booking in engineering_bookings]), 200
@app.route('/performance-bookings', methods=['GET'])
def get_performance_bookings():
    performance_bookings = PerformanceBooking.query.all()
    return jsonify([booking.to_dict() for booking in performance_bookings]), 200

@app.route('/contacts/<int:id>', methods=['PATCH'])
def update_contact_status(id):
    data = request.get_json()
    contact = Contact.query.get(id)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    # Update the status if provided
    if "status" in data:
        contact.status = data["status"]
    
    # Update the price if provided
    if "price" in data:
        try:
            contact.price = float(data["price"])
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400

    db.session.commit()
    return jsonify({"message": "Contact updated successfully!", "contact": contact.to_dict()}), 200



# Engineering Booking model
class EngineeringBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(80), nullable=False)
    client_email = db.Column(db.String(120), nullable=False)
    client_phone = db.Column(db.String(15), nullable=True)
    project_name = db.Column(db.String(120), nullable=False)
    project_manager = db.Column(db.String(80), nullable=True)
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
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_phone": self.client_phone,
            "project_name": self.project_name,
            "project_manager": self.project_manager,
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
        # Create a new EngineeringBooking instance
        new_booking = EngineeringBooking(
            client_name=data['clientName'],
            client_email=data['clientEmail'],
            client_phone=data.get('clientPhone'),
            project_name=data['projectName'],
            project_manager=data.get('projectManager'),
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

        return jsonify({"message": "Booking saved successfully!", "booking": new_booking.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/engineering-bookings/<int:id>', methods=['PATCH'])
def update_engineering_booking(id):
    data = request.get_json()
    booking = EngineeringBooking.query.get(id)
    if not booking:
        return jsonify({"error": "Engineering booking not found"}), 404

    # Update the status if provided
    if "status" in data:
        booking.status = data["status"]

    # Update the price if provided
    if "price" in data:
        try:
            booking.price = float(data["price"])
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400

    db.session.commit()
    return jsonify({"message": "Engineering booking updated successfully!", "booking": booking.to_dict()}), 200

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
# Performance Booking model
class PerformanceBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(80), nullable=False)
    client_email = db.Column(db.String(120), nullable=False)
    client_phone = db.Column(db.String(15), nullable=True)
    event_name = db.Column(db.String(120), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    event_date_time = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(255), nullable=False)
    guests = db.Column(db.String(10), nullable=True)
    special_requests = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)  # Renamed from price_range
    status = db.Column(db.String(50), nullable=False, default="Pending")  # Status field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "client_phone": self.client_phone,
            "event_name": self.event_name,
            "event_type": self.event_type,
            "event_date_time": self.event_date_time,
            "location": self.location,
            "guests": self.guests,
            "special_requests": self.special_requests,
            "price": self.price,  # Updated field
            "status": self.status,  # Include status
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


@app.route('/performance-bookings', methods=['POST'])
def save_performance_booking():
    data = request.get_json()
    try:
        new_booking = PerformanceBooking(
            client_name=data['clientName'],
            client_email=data['clientEmail'],
            client_phone=data.get('clientPhone'),
            event_name=data['eventName'],
            event_type=data['eventType'],
            event_date_time=data['eventDateTime'],
            location=data['location'],
            guests=data.get('guests'),
            special_requests=data.get('specialRequests'),
            price=data.get('price')  # Renamed field
        )
        db.session.add(new_booking)
        db.session.commit()
        return jsonify({"message": "Performance booking saved successfully!", "booking": new_booking.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/performance-bookings/<int:id>', methods=['PATCH'])
def update_performance_booking_status(id):
    data = request.get_json()
    booking = PerformanceBooking.query.get(id)
    if not booking:
        return jsonify({"error": "Performance booking not found"}), 404

    # Update the status if provided
    if "status" in data:
        booking.status = data["status"]

    # Update the price if provided
    if "price" in data:
        try:
            booking.price = float(data["price"])  # Renamed field
        except ValueError:
            return jsonify({"error": "Price must be a valid number"}), 400

    db.session.commit()
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


# Initialize database and run server
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
