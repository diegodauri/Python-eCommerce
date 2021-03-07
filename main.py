from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
import stripe

app = Flask(__name__)
stripe.api_key = 'sk_test_4eC39HqLyjWDarjtT1zdp7dc'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "fjdesfebniskd"
db = SQLAlchemy(app)


def stringToList(string):
    listRes = list(string.split(" "))
    return listRes


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    cart = db.relationship("Cart", uselist=False, backref="user")


class Products(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False, unique=True)
    description = db.Column(db.Text)
    image = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)


class Cart(db.Model):
    __tablename__ = 'cart'
    id = db.Column(db.Integer, primary_key=True)
    items = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def home():
    products = Products.query.all()
    return render_template("index.html", all_products=products)


@app.route("/product/<int:pid>")
def product(pid):
    product = Products.query.get(pid)
    return render_template("product.html", product=product)


@login_required
@app.route("/product/<int:pid>/add")
def add(pid):
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    product = Products.query.get(pid)
    cart.items = f"{cart.items} {product.id}"
    db.session.commit()
    flash(f"{product.name} added to shopping cart!")
    return redirect(url_for('home'))


@login_required
@app.route("/product/<int:pid>/remove")
def remove(pid):
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if str(pid) in cart.items:
        cart.items = cart.items.replace(str(pid), "")
        db.session.commit()
    return redirect(url_for("cart"))


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        password = request.form.get("password")
        email = request.form.get("email")

        if User.query.filter_by(email=email).first():
            flash("You've already signed up with that email, log in instead!")
            return render_template("signup.html")

        new_user = User(
            name=request.form.get("name"),
            email=email,
            password=generate_password_hash(password, method="pbkdf2:sha256", salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        new_cart = Cart(
            items="",
            user_id=current_user.id
        )
        db.session.add(new_cart)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("signup.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("home"))
            else:
                flash("Password incorrect, please try again.")
        else:
            flash("That email does not exist, please try again.")
    return render_template("login.html")


@login_required
@app.route("/cart")
def cart():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    items = stringToList(cart.items)
    all_items = [Products.query.get(item) for item in items if Products.query.get(item)]
    total = 0
    for item in all_items:
        total += item.price
    return render_template("cart.html", products=all_items, total=total)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out!")
    return redirect(url_for('home'))

@login_required
@app.route("/sucess")
def success():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    cart.items = ""
    db.session.commit()

    email_message = f"Subject:New Order\n\nHi {current_user.name}! We received your order! It will arrive to you in a few days."
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login("dauridiego.test@gmail.com", "Pa$$word1234")
        connection.sendmail("dauridiego.test@gmail.com", current_user.email, email_message)

    flash("Success, we sent you a confirmation email!")
    return redirect(url_for("home"))


@login_required
@app.route("/error")
def error():
    flash("Error, try again!")
    return redirect(url_for("home"))


@login_required
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    items = stringToList(cart.items)
    all_items = [Products.query.get(item) for item in items if Products.query.get(item)]
    total = 0
    checkout_items = []
    for item in all_items:
        schema = {
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': item.name,
                },
                'unit_amount': int(str(item.price) + "00"),
            },
            'quantity': 1,
        }

        checkout_items.append(schema)

    session = stripe.checkout.Session.create(
        payment_intent_data={
            'setup_future_usage': 'off_session',
        },
        customer_email=current_user.email,
        payment_method_types=['card'],
        line_items=checkout_items,
        mode='payment',
        success_url="http://localhost:5000/sucess",
        cancel_url='http://localhost:5000/error',
        shipping_address_collection={
            "allowed_countries": ['US', 'CA', "IT", "FR", "DE"],
        }
    )

    return jsonify(id=session.id)


if __name__ == "__main__":
    app.run(debug=True)
