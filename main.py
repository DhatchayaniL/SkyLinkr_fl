from flask import Flask, render_template, request, session, redirect, url_for
from pymongo import MongoClient
from bson import ObjectId, json_util

app = Flask(__name__)
app.secret_key = "your-secret-key"
client = MongoClient("mongodb+srv://dhat:lama123@cluster0.3tcoxvn.mongodb.net/?retryWrites=true&w=majority")
db = client.flight_ticket_booking
users_collection = db.users
bookings_collection = db.bookings
flights_collection = db.flights
admins_collection = db.admins

@app.route("/")
def home():
    return render_template("home.html")


# User routes
@app.route("/user/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        # Authenticate the user (you can use your own authentication mechanism)
        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username, "password": password})
        if user:
            session["user"] = str(user["_id"])  # Convert ObjectId to string
            return redirect(url_for("user_search_flights"))
        else:
            return render_template("user_login.html", error="Invalid username or password")

    return render_template("user_login.html")


@app.route("/user_signup", methods=["GET", "POST"])
def user_signup():
    if request.method == "POST":
        # Create a new user (you can define your own logic to store user information)
        username = request.form["username"]
        password = request.form["password"]

        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            return render_template("user_signup.html", error="Username already exists")

        user = {"username": username, "password": password}
        result = users_collection.insert_one(user)
        session["user"] = str(result.inserted_id)  # Convert ObjectId to string
        return redirect(url_for("user_search_flights"))

    return render_template("user_signup.html")


@app.route("/user_search_flights", methods=["GET", "POST"])
def user_search_flights():
    if request.method == "POST":
        # Search for flights based on from_place, to_place, date, seat_count, adult_count, and child_count
        from_place = request.form["from_place"]
        to_place = request.form["to_place"]
        date = request.form["date"]
        seat_count = int(request.form["seat_count"])
        adult_count = int(request.form["adult_count"])
        child_count = int(request.form["child_count"])

        flights = flights_collection.find({
            "from_place": from_place,
            "to_place": to_place,
            "date": date,
            "seat_count": {"$gte": seat_count},
        })

        for flight in flights:
            flight_id = flight["_id"]
            updated_seat_count = flight["seat_count"] - seat_count
            flights_collection.update_one({"_id": flight_id}, {"$set": {"seat_count": updated_seat_count}})

        updated_flights = flights_collection.find({
            "from_place": from_place,
            "to_place": to_place,
            "date": date,
            "seat_count": {"$gte": seat_count},
        })

        return render_template("user_search_flights.html", flights=updated_flights, seat_count=seat_count, adult_count=adult_count, child_count=child_count)

    return render_template("user_search_flights.html")





@app.route("/user_booking", methods=["POST"])
def user_booking():
    flight_id = request.form["flight_id"]

    flight = flights_collection.find_one({"_id": ObjectId(flight_id)})
    if not flight:
        return redirect(url_for("user_search_flights"))

    if flight["seat_count"] > 0:
        bookings_collection.insert_one({"user_id": ObjectId(session["user"]), "flight_id": ObjectId(flight_id)})
        flights_collection.update_one({"_id": ObjectId(flight_id)}, {"$inc": {"seat_count": -1}})

    return redirect(url_for("user_my_bookings"))

@app.route("/user/my_bookings")
def user_my_bookings():
    user_id = session.get("user")
    if user_id:
        bookings = bookings_collection.find({"user_id": ObjectId(user_id)})
        flights = []
        for booking in bookings:
            flight_id = booking["flight_id"]
            flight = flights_collection.find_one({"_id": flight_id})
            if flight:
                # seats_booked = booking.get("seats_booked", 0)
                # flight["seats_booked_by_user"] = seats_booked  
                # flight["seat_count"] = booking.get("seat_count", 0)         
                # flight["adult_count"] = booking.get("adult_count", 0) 
                # flight["child_count"] = booking.get("child_count", 0) 
                flights.append(flight)
        return render_template("user_my_bookings.html", flights=flights)

    return redirect(url_for("user_login"))



@app.route("/user/logout",  methods=["POST"])
def user_logout():
    session.pop("user", None)
    return redirect(url_for("home"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin@password":
            session["admin"] = username
            return redirect(url_for("admin_view_bookings"))
        else:
            return render_template("admin_login.html", error="Invalid username or password")

    return render_template("admin_login.html")


@app.route("/admin_add_flight", methods=["GET", "POST"])
def admin_add_flight():
    if request.method == "POST":

        flight_number = request.form["flight_number"]
        from_place = request.form["from_place"]
        to_place = request.form["to_place"]
        date = request.form["date"]
        time = request.form["time"]
        seat_count = int(request.form["seat_count"])

        flight = {
            "flight_number": flight_number,
            "from_place": from_place,
            "to_place": to_place,
            "date": date,
            "time": time,
            "seat_count": seat_count
        }
        flights_collection.insert_one(flight)

        return redirect(url_for("admin_view_bookings"))

    return render_template("admin_add_flight.html")




@app.route("/admin_remove_flight", methods=["GET", "POST"])
def admin_remove_flight():
    if request.method == "POST":
        flight_id = request.form["flight_id"]
        flights_collection.delete_one({"_id": ObjectId(flight_id)})

        bookings_collection.delete_many({"flight_id": ObjectId(flight_id)})

        return redirect(url_for("admin_view_bookings"))

    flights = flights_collection.find()
    return render_template("admin_remove_flight.html", flights=flights)


@app.route("/admin_view_bookings")
def admin_view_bookings():
    flights = list(flights_collection.find())
    bookings = list(bookings_collection.aggregate([
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user"
            }
        },
        {
            "$lookup": {
                "from": "flights",
                "localField": "flight_id",
                "foreignField": "_id",
                "as": "flight"
            }
        },
        {
            "$unwind": "$user"
        },
        {
            "$unwind": "$flight"
        }
    ]))

    return render_template("admin_view_bookings.html", flights=flights, bookings=bookings)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))



if __name__ == "__main__":
    app.run(debug=True)
