from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'   # change this to something secure

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'     # your MySQL username
app.config['MYSQL_PASSWORD'] = 'manager'     # your MySQL password
app.config['MYSQL_DB'] = 'motorbike_rental'

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('index.html')

from functools import wraps
from flask import abort

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session or session.get('role') != 'admin':
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function


# ✅ Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password,))
        account = cursor.fetchone()
        
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['fullname'] = account['fullname']
            session['email'] = account['email']
            session['role'] = account['role']
            return redirect(url_for('dashboard'))
        else:
            msg = 'Incorrect username/password!'
    return render_template('login.html', msg=msg)

# ✅ Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST' and 'fullname' in request.form and 'email' in request.form and 'password' in request.form:
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()

        if account:
            msg = 'Account already exists!'
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
        elif not fullname or not password or not email:
            msg = 'Please fill out the form!'
        else:
            cursor.execute('INSERT INTO users (fullname, email, password) VALUES (%s, %s, %s)', (fullname, email, password))
            mysql.connection.commit()
            msg = 'You have successfully registered!'
            return redirect(url_for('login'))
    return render_template('register.html', msg=msg)

from datetime import datetime

@app.route('/book/<int:bike_id>', methods=['GET', 'POST'])
def book_bike(bike_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM bikes WHERE id=%s", (bike_id,))
    bike = cursor.fetchone()

    if not bike or bike['status'] != 'available':
        return "Bike not available", 400

    msg = ''
    if request.method == 'POST':
        start_time_str = request.form['start_time']
        end_time_str = request.form['end_time']

        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
        duration_hours = (end_time - start_time).total_seconds() / 3600
        amount = round(duration_hours * float(bike['price_per_hour']), 2)

        # Insert booking
        cursor.execute(
            "INSERT INTO bookings (user_id, bike_id, start_time, end_time, amount) VALUES (%s, %s, %s, %s, %s)",
            (session['id'], bike_id, start_time, end_time, amount)
        )
        # Update bike status
        cursor.execute("UPDATE bikes SET status='rented' WHERE id=%s", (bike_id,))
        mysql.connection.commit()

        msg = f"Bike booked successfully! Total Amount: ₹{amount}"
        return render_template('booking_confirm.html', msg=msg)

    return render_template('book_bike.html', bike=bike)


@app.route('/admin/bikes')
@admin_required
def admin_bikes():

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM bikes")
    all_bikes = cursor.fetchall()
    return render_template('admin_bikes.html', bikes=all_bikes)


@app.route('/admin/add_bike', methods=['GET', 'POST'])
@admin_required
def add_bike():
    if request.method == 'POST':
        name = request.form['name']
        model = request.form['model']
        engine = request.form['engine']
        price = request.form['price']
        image = request.form['image']
        quantity = int(request.form['quantity'])

        cursor = mysql.connection.cursor()
        # Insert multiple bikes
        for _ in range(quantity):
            cursor.execute(
                "INSERT INTO bikes (name, model, engine, price_per_hour, image, status) VALUES (%s,%s,%s,%s,%s,'available')",
                (name, model, engine, price, image)
            )
        mysql.connection.commit()
        return redirect(url_for('admin_bikes'))

    return render_template('add_bike.html')

    return render_template('add_bike.html', msg=msg)


@app.route('/admin/update_bike/<int:bike_id>', methods=['GET', 'POST'])
@admin_required
def update_bike(bike_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM bikes WHERE id=%s", (bike_id,))
    bike = cursor.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        model = request.form['model']
        engine = request.form['engine']
        price = request.form['price']
        cursor.execute(
            "UPDATE bikes SET name=%s, model=%s, engine=%s, price_per_hour=%s WHERE id=%s",
            (name, model, engine, price, bike_id)
        )
        mysql.connection.commit()
        return redirect(url_for('admin_bikes'))

    return render_template('update_bike.html', bike=bike)


@app.route('/admin/delete_bike/<int:bike_id>')
@admin_required
def delete_bike(bike_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM bikes WHERE id=%s", (bike_id,))
    mysql.connection.commit()
    return redirect(url_for('admin_bikes'))

@app.route('/return/<int:booking_id>')
def return_bike(booking_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Get booking details
    cursor.execute("SELECT * FROM bookings WHERE id=%s", (booking_id,))
    booking = cursor.fetchone()

    if booking and booking['status'] == 'ongoing':
        cursor.execute("UPDATE bookings SET status='completed' WHERE id=%s", (booking_id,))
        cursor.execute("UPDATE bikes SET status='available' WHERE id=%s", (booking['bike_id'],))
        mysql.connection.commit()

    return redirect(url_for('dashboard'))


# ✅ Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Stats
        cursor.execute("SELECT COUNT(*) AS total FROM bikes")
        total_bikes = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS available FROM bikes WHERE status='available'")
        available_bikes = cursor.fetchone()['available']

        cursor.execute("SELECT COUNT(*) AS rented FROM bikes WHERE status='rented'")
        rented_bikes = cursor.fetchone()['rented']

        cursor.execute("SELECT COALESCE(SUM(amount),0) AS total_earnings FROM bookings WHERE status='completed'")
        total_earnings = cursor.fetchone()['total_earnings']

        cursor.execute("""
            SELECT bk.name, COUNT(*) AS times_rented 
            FROM bookings bo 
            JOIN bikes bk ON bo.bike_id=bk.id 
            GROUP BY bk.name 
            ORDER BY times_rented DESC LIMIT 5
        """)
        popular_bikes = cursor.fetchall()
        cursor.execute("""
            SELECT model, COUNT(*) AS total_bikes,
                SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available_bikes,
                SUM(CASE WHEN status='rented' THEN 1 ELSE 0 END) AS rented_bikes
            FROM bikes
            GROUP BY model
        """)
        bikes_per_model = cursor.fetchall()
        cursor.execute("""
            SELECT model, COUNT(*) AS total_bikes,
                SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available_bikes,
                SUM(CASE WHEN status='rented' THEN 1 ELSE 0 END) AS rented_bikes,
                MAX(name) AS bike_name, MAX(engine) AS engine, MAX(price_per_hour) AS price_per_hour, MAX(image) AS image
            FROM bikes
            GROUP BY model
        """)
        bikes_grouped = cursor.fetchall()


        cursor.execute("""
            SELECT bo.id, u.fullname AS user_name, bk.name AS bike_name, bk.model, bo.start_time, bo.end_time, bo.amount, bo.status
            FROM bookings bo
            JOIN users u ON bo.user_id = u.id
            JOIN bikes bk ON bo.bike_id = bk.id
            ORDER BY bo.start_time DESC
        """)
        bookings = cursor.fetchall()
        
        cursor.execute("""
            SELECT model, COUNT(*) AS total_bikes,
                SUM(CASE WHEN status='rented' THEN 1 ELSE 0 END) AS rented_bikes,
                SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available_bikes
            FROM bikes
            GROUP BY model
        """)
        bikes_per_model = cursor.fetchall()


        return render_template('dashboard.html',
                               total_bikes=total_bikes,
                               available_bikes=available_bikes,
                               rented_bikes=rented_bikes,
                               total_earnings=total_earnings,
                               popular_bikes=popular_bikes,
                               bookings=bookings)
    return redirect(url_for('login'))



@app.route('/bikes')
def bikes():
    if 'loggedin' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM bikes ORDER BY id ASC")
    all_bikes = cursor.fetchall()
    return render_template('bikes.html', bikes=all_bikes)



# ✅ Logout route
@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('email', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
