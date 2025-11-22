from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # Change this for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    seat_count = db.Column(db.Integer, nullable=False)
    seats = db.relationship('Seat', backref='classroom', lazy=True)

class Seat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    classroom_id = db.Column(db.Integer, db.ForeignKey('classroom.id'), nullable=False)
    seat_number = db.Column(db.Integer, nullable=False)
    # Current status can be cached here for performance, but we'll rely on latest update for now or a separate status field
    # Let's add a current_status field for quick access
    current_status = db.Column(db.String(20), default='free') # 'free', 'occupied'
    last_update_time = db.Column(db.DateTime, default=datetime.utcnow)

class SeatUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seat.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# --- Helper Functions ---

def get_prediction(classroom_id):
    # Simple prediction logic based on historical data for the current hour
    now = datetime.utcnow()
    current_hour = now.hour
    
    # Find all updates for this classroom's seats in the past 30 days at this hour
    # This is a simplified query. In a real app, we'd do more complex aggregation.
    
    # For this prototype, let's look at the average occupancy of the room at this hour
    # We can query SeatUpdates joined with Seat for this classroom, filtered by hour
    
    # Simplified approach:
    # Get total seats
    room = Classroom.query.get(classroom_id)
    if not room:
        return "Unknown"
        
    total_seats = room.seat_count
    
    # Count how many seats are CURRENTLY occupied (Real-time)
    occupied_count = Seat.query.filter_by(classroom_id=classroom_id, current_status='occupied').count()
    occupancy_rate = (occupied_count / total_seats) * 100 if total_seats > 0 else 0
    
    # Prediction text
    if occupancy_rate > 70:
        return "High occupancy expected"
    elif occupancy_rate > 30:
        return "Moderate occupancy expected"
    else:
        return "Low occupancy expected"

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return render_template('auth.html', error="Invalid credentials", mode='login')
    return render_template('auth.html', mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
             return render_template('auth.html', error="Username already exists", mode='register')
             
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('auth.html', mode='register')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    classrooms = Classroom.query.all()
    rooms_data = []
    for room in classrooms:
        prediction = get_prediction(room.id)
        occupied = Seat.query.filter_by(classroom_id=room.id, current_status='occupied').count()
        rooms_data.append({
            'id': room.id,
            'name': room.name,
            'total': room.seat_count,
            'occupied': occupied,
            'prediction': prediction
        })
        
    return render_template('dashboard.html', rooms=rooms_data)

@app.route('/room/<int:room_id>')
def room(room_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    room = Classroom.query.get_or_404(room_id)
    seats = Seat.query.filter_by(classroom_id=room_id).all()
    prediction = get_prediction(room_id)
    
    return render_template('room.html', room=room, seats=seats, prediction=prediction)

@app.route('/api/update_seat', methods=['POST'])
def update_seat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    seat_id = data.get('seat_id')
    status = data.get('status')
    
    seat = Seat.query.get(seat_id)
    if not seat:
        return jsonify({'error': 'Seat not found'}), 404
        
    # Update current status
    seat.current_status = status
    seat.last_update_time = datetime.utcnow()
    
    # Log history
    update = SeatUpdate(
        seat_id=seat_id,
        user_id=session['user_id'],
        status=status
    )
    
    db.session.add(update)
    db.session.commit()
    
    return jsonify({'success': True})

# --- Init DB ---
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create dummy data if empty
        if not Classroom.query.first():
            # Create Classrooms
            c1 = Classroom(name="Room 204 (Lab)", seat_count=20)
            c2 = Classroom(name="Library Study Hall", seat_count=50)
            c3 = Classroom(name="Room 101 (Lecture)", seat_count=30)
            db.session.add_all([c1, c2, c3])
            db.session.commit()
            
            # Create Seats for each classroom
            for c in [c1, c2, c3]:
                for i in range(1, c.seat_count + 1):
                    seat = Seat(classroom_id=c.id, seat_number=i)
                    db.session.add(seat)
            db.session.commit()
            print("Database initialized with dummy data.")

if __name__ == '__main__':
    if not os.path.exists('database.db'):
        init_db()
    app.run(debug=True)
