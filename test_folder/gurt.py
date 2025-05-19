"""
ClimbOn - Climbing Progress Tracker
A professional climbing tracking app with social features and performance analysis.
"""

import os
from datetime import datetime, timedelta
import json
import random
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, desc, or_
import plotly
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import numpy as np

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_for_development')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///climbon.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Climbing grade mapping (V-scale to points)
GRADE_POINTS = {
    'VB': 10, 'V0': 20, 'V1': 30, 'V2': 40, 'V3': 50, 'V4': 60,
    'V5': 70, 'V6': 80, 'V7': 90, 'V8': 100, 'V9': 110, 'V10': 120,
    'V11': 130, 'V12': 140, 'V13': 150, 'V14': 160, 'V15': 170, 'V16': 180,
    'V17': 190
}

# Climbing tips by category
CLIMBING_TIPS = {
    'strength': [
        "Try incorporating hangboard training 2-3 times a week to improve finger strength.",
        "Campus board exercises can help develop dynamic power moves.",
        "Add antagonist training to prevent injuries - pushups and dips are good options.",
        "Work on lock-off strength with one-arm pull-up progressions.",
        "Consider weighted pull-ups to build upper body strength."
    ],
    'technique': [
        "Focus on silent foot placement to improve precision.",
        "Practice 'quiet feet' drills where you make no noise when placing your feet.",
        "Work on flagging techniques to improve balance on overhanging routes.",
        "Try climbs with 'no readjusting' - place your hands and feet once and commit.",
        "Practice climbing slowly and deliberately to improve movement efficiency."
    ],
    'endurance': [
        "Try '4x4s' - climb four problems four times with minimal rest.",
        "Work on circuit training - linking multiple boulder problems together.",
        "Try 'pyramid' workouts - climb increasing and then decreasing grades with minimal rest.",
        "Incorporate ARC training (Aerobic Restoration and Capillarity) for forearm endurance.",
        "Focus on breathing techniques while climbing to improve stamina."
    ],
    'mental': [
        "Practice visualization techniques before attempting hard projects.",
        "Work on mindfulness to stay present during challenging climbs.",
        "Set specific, achievable goals for each climbing session.",
        "Try 'falling practice' to overcome fear of falling.",
        "Work on breathing techniques to maintain composure on difficult moves."
    ],
    'flexibility': [
        "Add regular hip mobility exercises to your routine.",
        "Practice dynamic stretching before climbing and static stretching after.",
        "Work on hamstring flexibility to improve high stepping.",
        "Focus on shoulder mobility to help with reach moves.",
        "Try yoga poses that emphasize hip opening and shoulder flexibility."
    ]
}


# Define Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    bio = db.Column(db.Text)
    profile_picture = db.Column(db.String(255), default='default_profile.png')
    location = db.Column(db.String(100))
    climbing_since = db.Column(db.DateTime)
    favorite_gym = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    routes = db.relationship('Route', backref='climber', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_weekly_points(self):
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        routes = Route.query.filter_by(user_id=self.id).filter(Route.date >= one_week_ago).all()
        return sum(GRADE_POINTS.get(route.grade, 0) for route in routes)

    @property
    def climbing_experience_years(self):
        if self.climbing_since:
            delta = datetime.utcnow() - self.climbing_since
            return round(delta.days / 365, 1)
        return 0


class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(10), nullable=False)  # VB, V0, V1, etc.
    style = db.Column(db.String(50))  # Slab, Vertical, Overhang, Roof, etc.
    hold_types = db.Column(db.String(100))  # Crimps, Slopers, Jugs, Pinches, etc.
    personal_difficulty = db.Column(db.Integer)  # Scale of 1-10
    attempts = db.Column(db.Integer, default=1)
    sent = db.Column(db.Boolean, default=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(100))  # Gym name or outdoor area
    notes = db.Column(db.Text)
    photo_url = db.Column(db.String(255))

    @property
    def v_points(self):
        return GRADE_POINTS.get(self.grade, 0)


class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/dashboard')
@login_required
def dashboard():
    # Get recent routes
    recent_routes = Route.query.filter_by(user_id=current_user.id).order_by(Route.date.desc()).limit(5).all()

    # Get climbing stats
    total_routes = Route.query.filter_by(user_id=current_user.id).count()
    total_points = sum(GRADE_POINTS.get(route.grade, 0) for route in
                       Route.query.filter_by(user_id=current_user.id).all())

    # Get highest grade climbed
    highest_grade_route = Route.query.filter_by(user_id=current_user.id, sent=True).order_by(
        desc(Route.grade)).first()
    highest_grade = highest_grade_route.grade if highest_grade_route else "N/A"

    # Generate personalized tip
    tip_category = random.choice(list(CLIMBING_TIPS.keys()))
    personalized_tip = random.choice(CLIMBING_TIPS[tip_category])

    # Get friends' recent activity
    friend_ids = [friendship.friend_id for friendship in
                  Friendship.query.filter_by(user_id=current_user.id, status='accepted').all()]

    friends_activity = []
    if friend_ids:
        friends_routes = Route.query.filter(Route.user_id.in_(friend_ids)).order_by(
            Route.date.desc()).limit(10).all()

        for route in friends_routes:
            friend = User.query.get(route.user_id)
            friends_activity.append({
                'friend_name': friend.username,
                'route_name': route.name,
                'grade': route.grade,
                'date': route.date
            })

    # Generate graphs data
    graphs = generate_dashboard_graphs(current_user.id)

    return render_template('dashboard.html',
                           recent_routes=recent_routes,
                           total_routes=total_routes,
                           total_points=total_points,
                           highest_grade=highest_grade,
                           personalized_tip=personalized_tip,
                           friends_activity=friends_activity,
                           graphs=graphs)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form

        user = User.query.filter(or_(User.username == username, User.email == username)).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')

        user_exists = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if user_exists:
            flash('Username or email already exists', 'danger')
            return render_template('register.html')

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio')
        current_user.location = request.form.get('location')
        current_user.favorite_gym = request.form.get('favorite_gym')

        climbing_since = request.form.get('climbing_since')
        if climbing_since:
            current_user.climbing_since = datetime.strptime(climbing_since, '%Y-%m-%d')

        # Handle profile picture upload here if implemented

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=current_user)


@app.route('/add_route', methods=['GET', 'POST'])
@login_required
def add_route():
    if request.method == 'POST':
        name = request.form.get('name')
        grade = request.form.get('grade')
        style = request.form.get('style')
        hold_types = request.form.get('hold_types')
        personal_difficulty = int(request.form.get('personal_difficulty'))
        attempts = int(request.form.get('attempts'))
        sent = 'sent' in request.form
        location = request.form.get('location')
        notes = request.form.get('notes')

        # Handle photo upload if implemented
        photo_url = None

        new_route = Route(
            user_id=current_user.id,
            name=name,
            grade=grade,
            style=style,
            hold_types=hold_types,
            personal_difficulty=personal_difficulty,
            attempts=attempts,
            sent=sent,
            location=location,
            notes=notes,
            photo_url=photo_url
        )

        db.session.add(new_route)
        db.session.commit()

        flash('Route added successfully!', 'success')
        return redirect(url_for('logbook'))

    return render_template('add_route.html')


@app.route('/logbook')
@login_required
def logbook():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    routes = Route.query.filter_by(user_id=current_user.id).order_by(
        Route.date.desc()).paginate(page=page, per_page=per_page)

    return render_template('logbook.html', routes=routes)


@app.route('/route/<int:route_id>')
@login_required
def view_route(route_id):
    route = Route.query.get_or_404(route_id)

    if route.user_id != current_user.id:
        flash('You do not have permission to view this route.', 'danger')
        return redirect(url_for('logbook'))

    return render_template('view_route.html', route=route)


@app.route('/route/<int:route_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_route(route_id):
    route = Route.query.get_or_404(route_id)

    if route.user_id != current_user.id:
        flash('You do not have permission to edit this route.', 'danger')
        return redirect(url_for('logbook'))

    if request.method == 'POST':
        route.name = request.form.get('name')
        route.grade = request.form.get('grade')
        route.style = request.form.get('style')
        route.hold_types = request.form.get('hold_types')
        route.personal_difficulty = int(request.form.get('personal_difficulty'))
        route.attempts = int(request.form.get('attempts'))
        route.sent = 'sent' in request.form
        route.location = request.form.get('location')
        route.notes = request.form.get('notes')

        # Handle photo update if implemented

        db.session.commit()
        flash('Route updated successfully!', 'success')
        return redirect(url_for('view_route', route_id=route_id))

    return render_template('edit_route.html', route=route)


@app.route('/route/<int:route_id>/delete', methods=['POST'])
@login_required
def delete_route(route_id):
    route = Route.query.get_or_404(route_id)

    if route.user_id != current_user.id:
        flash('You do not have permission to delete this route.', 'danger')
        return redirect(url_for('logbook'))

    db.session.delete(route)
    db.session.commit()

    flash('Route deleted successfully!', 'success')
    return redirect(url_for('logbook'))


@app.route('/stats')
@login_required
def stats():
    # Generate statistics graphs
    graphs = generate_stats_graphs(current_user.id)

    # Get general statistics
    total_climbs = Route.query.filter_by(user_id=current_user.id).count()
    sent_climbs = Route.query.filter_by(user_id=current_user.id, sent=True).count()

    success_rate = (sent_climbs / total_climbs * 100) if total_climbs > 0 else 0

    # Get favorite climbing style
    favorite_style = db.session.query(
        Route.style, func.count(Route.id).label('count')
    ).filter_by(user_id=current_user.id).group_by(Route.style).order_by(desc('count')).first()

    favorite_style = favorite_style[0] if favorite_style else "N/A"

    # Get average attempts per send
    avg_attempts = db.session.query(func.avg(Route.attempts)).filter_by(
        user_id=current_user.id, sent=True).scalar()
    avg_attempts = round(avg_attempts, 1) if avg_attempts else 0

    # Generate personalized tips based on the user's climbing data
    tips = generate_personalized_tips(current_user.id)

    return render_template('stats.html',
                           graphs=graphs,
                           total_climbs=total_climbs,
                           sent_climbs=sent_climbs,
                           success_rate=round(success_rate, 1),
                           favorite_style=favorite_style,
                           avg_attempts=avg_attempts,
                           tips=tips)


@app.route('/friends')
@login_required
def friends():
    # Get accepted friends
    friends_data = []
    friendships = Friendship.query.filter_by(user_id=current_user.id, status='accepted').all()

    for friendship in friendships:
        friend = User.query.get(friendship.friend_id)
        weekly_points = friend.get_weekly_points()
        recent_send = Route.query.filter_by(user_id=friend.id, sent=True).order_by(
            Route.date.desc()).first()

        friends_data.append({
            'id': friend.id,
            'username': friend.username,
            'profile_picture': friend.profile_picture,
            'weekly_points': weekly_points,
            'recent_send': recent_send.grade if recent_send else "N/A"
        })

    # Sort by weekly points for leaderboard
    friends_data.sort(key=lambda x: x['weekly_points'], reverse=True)

    # Add current user to the leaderboard
    my_weekly_points = current_user.get_weekly_points()
    my_recent_send = Route.query.filter_by(user_id=current_user.id, sent=True).order_by(
        Route.date.desc()).first()

    my_data = {
        'id': current_user.id,
        'username': current_user.username + " (You)",
        'profile_picture': current_user.profile_picture,
        'weekly_points': my_weekly_points,
        'recent_send': my_recent_send.grade if my_recent_send else "N/A"
    }

    friends_data.append(my_data)
    friends_data.sort(key=lambda x: x['weekly_points'], reverse=True)

    # Get pending friend requests
    pending_requests = []
    pending = Friendship.query.filter_by(friend_id=current_user.id, status='pending').all()

    for request in pending:
        user = User.query.get(request.user_id)
        pending_requests.append({
            'id': request.id,
            'username': user.username,
            'profile_picture': user.profile_picture
        })

    return render_template('friends.html',
                           friends=friends_data,
                           pending_requests=pending_requests)


@app.route('/search_users')
@login_required
def search_users():
    query = request.args.get('query', '')

    if not query:
        return jsonify([])

    users = User.query.filter(
        User.username.ilike(f'%{query}%') & (User.id != current_user.id)
    ).limit(10).all()

    results = []
    for user in users:
        # Check if already friends or request pending
        existing = Friendship.query.filter(
            ((Friendship.user_id == current_user.id) & (Friendship.friend_id == user.id)) |
            ((Friendship.user_id == user.id) & (Friendship.friend_id == current_user.id))
        ).first()

        status = existing.status if existing else "none"

        results.append({
            'id': user.id,
            'username': user.username,
            'profile_picture': user.profile_picture,
            'status': status
        })

    return jsonify(results)


@app.route('/add_friend/<int:user_id>', methods=['POST'])
@login_required
def add_friend(user_id):
    if user_id == current_user.id:
        return jsonify({'status': 'error', 'message': 'Cannot add yourself as a friend'})

    # Check if friendship already exists
    existing = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == user_id)) |
        ((Friendship.user_id == user_id) & (Friendship.friend_id == current_user.id))
    ).first()

    if existing:
        return jsonify({'status': 'error', 'message': 'Friend request already exists'})

    new_friendship = Friendship(user_id=current_user.id, friend_id=user_id)
    db.session.add(new_friendship)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Friend request sent'})


@app.route('/accept_friend/<int:request_id>', methods=['POST'])
@login_required
def accept_friend(request_id):
    request = Friendship.query.get_or_404(request_id)

    if request.friend_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Not authorized'})

    request.status = 'accepted'

    # Create reverse friendship
    reverse_friendship = Friendship(
        user_id=current_user.id,
        friend_id=request.user_id,
        status='accepted'
    )
    db.session.add(reverse_friendship)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Friend request accepted'})


@app.route('/reject_friend/<int:request_id>', methods=['POST'])
@login_required
def reject_friend(request_id):
    request = Friendship.query.get_or_404(request_id)

    if request.friend_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Not authorized'})

    request.status = 'rejected'
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Friend request rejected'})


@app.route('/friend_profile/<int:user_id>')
@login_required
def friend_profile(user_id):
    friend = User.query.get_or_404(user_id)

    # Check if they are friends
    friendship = Friendship.query.filter_by(
        user_id=current_user.id, friend_id=user_id, status='accepted'
    ).first()

    if not friendship and user_id != current_user.id:
        flash('You are not friends with this user.', 'danger')
        return redirect(url_for('friends'))

    # Get friend's recent climbs
    recent_routes = Route.query.filter_by(user_id=user_id).order_by(
        Route.date.desc()).limit(5).all()

    # Get friend's stats
    total_routes = Route.query.filter_by(user_id=user_id).count()
    highest_grade_route = Route.query.filter_by(user_id=user_id, sent=True).order_by(
        desc(Route.grade)).first()
    highest_grade = highest_grade_route.grade if highest_grade_route else "N/A"

    # Generate friend's visualization
    graphs = generate_friend_graphs(user_id)

    return render_template('friend_profile.html',
                           friend=friend,
                           recent_routes=recent_routes,
                           total_routes=total_routes,
                           highest_grade=highest_grade,
                           graphs=graphs)


# Helper functions for generating data visualizations
def generate_dashboard_graphs(user_id):
    # Get route data for the past 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    routes = Route.query.filter_by(user_id=user_id).filter(Route.date >= thirty_days_ago).all()

    if not routes:
        return {}

    # Convert to DataFrame for easier manipulation
    data = []
    for route in routes:
        data.append({
            'date': route.date,
            'grade': route.grade,
            'points': GRADE_POINTS.get(route.grade, 0),
            'sent': route.sent,
            'style': route.style,
            'personal_difficulty': route.personal_difficulty
        })

    df = pd.DataFrame(data)

    # Progress over time graph
    if not df.empty:
        df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
        daily_summary = df.groupby('date_str').agg({'points': 'sum'}).reset_index()
        daily_summary = daily_summary.sort_values('date_str')

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=daily_summary['date_str'],
            y=daily_summary['points'],
            mode='lines+markers',
            name='Daily Points',
            line=dict(color='#FF5733', width=3),
            marker=dict(size=8, color='#FFC300')
        ))

        fig1.update_layout(
            title='Climbing Points Over Time',
            xaxis_title='Date',
            yaxis_title='V-Points',
            template='plotly_dark',
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        progress_graph = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        progress_graph = None

    # Grade distribution graph
    if not df.empty:
        grade_counts = df[df['sent'] == True].groupby('grade').size().reset_index(name='count')

        # Sort grades properly
        grade_order = sorted(list(GRADE_POINTS.keys()), key=lambda x: GRADE_POINTS[x])
        grade_counts['grade'] = pd.Categorical(grade_counts['grade'], categories=grade_order, ordered=True)
        grade_counts = grade_counts.sort_values('grade')

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=grade_counts['grade'],
            y=grade_counts['count'],
            marker_color='#3498DB',
            text=grade_counts['count'],
            textposition='auto'
        ))

        fig2.update_layout(
            title='Sent Grades Distribution',
            xaxis_title='Grade',
            yaxis_title='Number of Climbs',
            template='plotly_dark',
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        grade_graph = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        grade_graph = None

    return {
        'progress_graph': progress_graph,
        'grade_graph': grade_graph
    }


def generate_stats_graphs(user_id):
    # Get all user routes
    routes = Route.query.filter_by(user_id=user_id).all()

    if not routes:
        return {}

    # Convert to DataFrame
    data = []
    for route in routes:
        data.append({
            'date': route.date,
            'grade': route.grade,
            'points': GRADE_POINTS.get(route.grade, 0),
            'sent': route.sent,
            'style': route.style,
            'personal_difficulty': route.personal_difficulty,
            'attempts': route.attempts,
            'hold_types': route.hold_types
        })

    df = pd.DataFrame(data)

    # For time series analysis, group by month
    if not df.empty:
        df['month'] = df['date'].dt.strftime('%Y-%m')
        monthly_progress = df.groupby('month').agg(
            avg_grade_points=('points', 'mean'),
            total_climbs=('grade', 'count')
        ).reset_index()

        fig1 = go.Figure()

        fig1.add_trace(go.Scatter(
            x=monthly_progress['month'],
            y=monthly_progress['avg_grade_points'],
            mode='lines+markers',
            name='Avg Grade Points',
            line=dict(color='#FF5733', width=3),
            marker=dict(size=8)
        ))

        fig1.add_trace(go.Bar(
            x=monthly_progress['month'],
            y=monthly_progress['total_climbs'],
            name='Total Climbs',
            marker_color='rgba(52, 152, 219, 0.7)',
            yaxis='y2'
        ))

        fig1.update_layout(
            title='Progress Over Time',
            xaxis_title='Month',
            yaxis_title='Average Grade Points',
            yaxis2=dict(
                title='Total Climbs',
                overlaying='y',
                side='right'
            ),
            legend=dict(x=0.01, y=0.99),
            template='plotly_dark',
            height=500,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        progress_graph = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        progress_graph = None

    # Style performance analysis
    if not df.empty and 'style' in df.columns:
        style_performance = df[df['sent'] == True].groupby('style').agg(
            avg_grade_points=('points', 'mean'),
            count=('style', 'count')
        ).reset_index()

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=style_performance['style'],
            y=style_performance['avg_grade_points'],
            marker_color='#2ECC71',
            name='Avg Grade Points',
            text=style_performance['avg_grade_points'].round(1),
            textposition='auto'
        ))

        fig2.add_trace(go.Scatter(
            x=style_performance['style'],
            y=style_performance['count'],
            mode='markers',
            name='Number of Climbs',
            marker=dict(
                size=style_performance['count'] * 3,
                color='#F39C12',
                line=dict(width=2, color='#E67E22')
            ),
            yaxis='y2'
        ))

        fig2.update_layout(
            title='Performance by Climbing Style',
            xaxis_title='Style',
            yaxis_title='Average Grade Points',
            yaxis2=dict(
                title='Number of Climbs',
                overlaying='y',
                side='right'
            ),
            legend=dict(x=0.01, y=0.99),
            template='plotly_dark',
            height=500,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        style_graph = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        style_graph = None

    # Grade attempts correlation
    if not df.empty:
        sent_routes = df[df['sent'] == True]
        if not sent_routes.empty:
            # Group by grade and calculate average attempts
            grade_attempts = sent_routes.groupby('grade').agg(
                avg_attempts=('attempts', 'mean'),
                count=('grade', 'count')
            ).reset_index()

            # Sort grades properly
            grade_order = sorted(list(GRADE_POINTS.keys()), key=lambda x: GRADE_POINTS[x])
            grade_attempts['grade'] = pd.Categorical(grade_attempts['grade'], categories=grade_order, ordered=True)
            grade_attempts = grade_attempts.sort_values('grade')

            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=grade_attempts['grade'],
                y=grade_attempts['avg_attempts'],
                marker_color='#9B59B6',
                text=grade_attempts['avg_attempts'].round(1),
                textposition='auto'
            ))

            fig3.update_layout(
                title='Average Attempts by Grade',
                xaxis_title='Grade',
                yaxis_title='Average Attempts to Send',
                template='plotly_dark',
                height=400,
                margin=dict(l=50, r=50, t=80, b=50),
                paper_bgcolor='rgba(40, 44, 52, 1)',
                plot_bgcolor='rgba(40, 44, 52, 1)',
                font=dict(color='white')
            )

            attempts_graph = json.dumps(fig3, cls=plotly.utils.PlotlyJSONEncoder)
        else:
            attempts_graph = None
    else:
        attempts_graph = None

    # Personal difficulty vs actual grade
    if not df.empty and 'personal_difficulty' in df.columns:
        # Calculate average personal difficulty per grade
        difficulty_by_grade = df.groupby('grade').agg(
            avg_difficulty=('personal_difficulty', 'mean'),
            count=('grade', 'count')
        ).reset_index()

        # Sort grades properly
        grade_order = sorted(list(GRADE_POINTS.keys()), key=lambda x: GRADE_POINTS[x])
        difficulty_by_grade['grade'] = pd.Categorical(difficulty_by_grade['grade'], categories=grade_order,
                                                      ordered=True)
        difficulty_by_grade = difficulty_by_grade.sort_values('grade')

        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=difficulty_by_grade['grade'],
            y=difficulty_by_grade['avg_difficulty'],
            mode='lines+markers',
            name='Avg Perceived Difficulty',
            line=dict(color='#E74C3C', width=3),
            marker=dict(
                size=difficulty_by_grade['count'] * 2,
                color='#C0392B',
                line=dict(width=2, color='#A93226')
            )
        ))

        # Add theoretical diagonal line (if grade matches personal difficulty)
        grade_points = [GRADE_POINTS[g] / 10 for g in difficulty_by_grade['grade']]
        fig4.add_trace(go.Scatter(
            x=difficulty_by_grade['grade'],
            y=grade_points,
            mode='lines',
            name='Expected Difficulty',
            line=dict(color='rgba(149, 165, 166, 0.5)', width=2, dash='dash')
        ))

        fig4.update_layout(
            title='Perceived Difficulty vs Actual Grade',
            xaxis_title='Grade',
            yaxis_title='Perceived Difficulty (1-10)',
            template='plotly_dark',
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        difficulty_graph = json.dumps(fig4, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        difficulty_graph = None

    return {
        'progress_graph': progress_graph,
        'style_graph': style_graph,
        'attempts_graph': attempts_graph,
        'difficulty_graph': difficulty_graph
    }


def generate_friend_graphs(user_id):
    # Get all routes for the friend
    routes = Route.query.filter_by(user_id=user_id).all()

    if not routes:
        return {}

    # Convert to DataFrame
    data = []
    for route in routes:
        data.append({
            'date': route.date,
            'grade': route.grade,
            'points': GRADE_POINTS.get(route.grade, 0),
            'sent': route.sent,
            'style': route.style
        })

    df = pd.DataFrame(data)

    # Progress over time
    if not df.empty:
        # Group by week
        df['week'] = df['date'].dt.strftime('%Y-%U')
        weekly_progress = df.groupby('week').agg(
            total_points=('points', 'sum'),
            highest_grade=('points', 'max')
        ).reset_index()

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=weekly_progress['week'],
            y=weekly_progress['total_points'],
            mode='lines+markers',
            name='Weekly Points',
            line=dict(color='#FF5733', width=3),
            marker=dict(size=8)
        ))

        fig1.update_layout(
            title='Weekly Climbing Progress',
            xaxis_title='Week',
            yaxis_title='Total Points',
            template='plotly_dark',
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        progress_graph = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        progress_graph = None

    # Grade distribution
    if not df.empty:
        grade_counts = df[df['sent'] == True].groupby('grade').size().reset_index(name='count')

        # Sort grades properly
        grade_order = sorted(list(GRADE_POINTS.keys()), key=lambda x: GRADE_POINTS[x])
        grade_counts['grade'] = pd.Categorical(grade_counts['grade'], categories=grade_order, ordered=True)
        grade_counts = grade_counts.sort_values('grade')

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=grade_counts['grade'],
            y=grade_counts['count'],
            marker_color='#3498DB',
            text=grade_counts['count'],
            textposition='auto'
        ))

        fig2.update_layout(
            title='Sent Grades Distribution',
            xaxis_title='Grade',
            yaxis_title='Number of Climbs',
            template='plotly_dark',
            height=400,
            margin=dict(l=50, r=50, t=80, b=50),
            paper_bgcolor='rgba(40, 44, 52, 1)',
            plot_bgcolor='rgba(40, 44, 52, 1)',
            font=dict(color='white')
        )

        grade_graph = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        grade_graph = None

    return {
        'progress_graph': progress_graph,
        'grade_graph': grade_graph
    }


def generate_personalized_tips(user_id):
    """Generate personalized climbing tips based on user data"""
    tips = []

    # Get routes for analysis
    routes = Route.query.filter_by(user_id=user_id).all()

    if not routes:
        # If no routes, provide general tips
        return [random.choice(CLIMBING_TIPS[category]) for category in list(CLIMBING_TIPS.keys())[:3]]

    # Convert to DataFrame
    data = []
    for route in routes:
        data.append({
            'date': route.date,
            'grade': route.grade,
            'points': GRADE_POINTS.get(route.grade, 0),
            'sent': route.sent,
            'style': route.style,
            'personal_difficulty': route.personal_difficulty,
            'attempts': route.attempts,
            'hold_types': route.hold_types
        })

    df = pd.DataFrame(data)

    # Analyze climbing style performance
    if 'style' in df.columns and not df.empty:
        style_performance = df[df['sent'] == True].groupby('style').agg(
            avg_grade_points=('points', 'mean'),
            count=('style', 'count')
        ).reset_index()

        if not style_performance.empty and len(style_performance) > 1:
            # Find weakest style (lowest average grade points with reasonable sample size)
            style_performance = style_performance[style_performance['count'] >= 3]
            if not style_performance.empty:
                weakest_style = style_performance.loc[style_performance['avg_grade_points'].idxmin()]['style']

                if weakest_style in ['Slab', 'Vertical']:
                    tips.append(
                        "Your slab/vertical climbing could use work. Focus on foot placement and balance drills.")
                elif weakest_style in ['Overhang', 'Roof']:
                    tips.append("Your overhang climbing needs improvement. Work on core strength and power endurance.")
                elif weakest_style in ['Dynamic', 'Dyno']:
                    tips.append("You could improve at dynamic moves. Practice controlled dynos and power training.")
                elif weakest_style in ['Technical', 'Crimpy']:
                    tips.append(
                        "Your technical climbing on small holds could use work. Try finger strength and precise footwork drills.")

    # Analyze grade plateau
    if not df.empty and len(df) >= 10:
        # Sort by date
        df = df.sort_values('date')

        # Get max grade points for each month
        df['month'] = df['date'].dt.strftime('%Y-%m')
        monthly_max = df[df['sent'] == True].groupby('month').agg(max_points=('points', 'max')).reset_index()

        if len(monthly_max) >= 3:
            # Check if max grade has plateaued
            recent_months = monthly_max.tail(3)
            if recent_months['max_points'].std() < 5:  # Low standard deviation indicates plateau
                tips.append(
                    "You seem to have plateaued. Try projecting routes 1-2 grades harder than your current level.")

    # Check attempts pattern
    if 'attempts' in df.columns and not df.empty:
        avg_attempts = df[df['sent'] == True]['attempts'].mean()

        if avg_attempts < 1.5:
            tips.append(
                "You send most routes quickly. Challenge yourself with harder grades to improve strength and technique.")
        elif avg_attempts > 5:
            tips.append(
                "You're spending many attempts on routes. Focus on efficient movement and reading routes before climbing.")

    # Check climbing frequency
    if not df.empty and len(df) >= 5:
        # Get dates of climbs
        dates = df['date'].dt.date.unique()
        dates = sorted(dates)

        if len(dates) >= 2:
            # Calculate average days between sessions
            days_between = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            avg_days = sum(days_between) / len(days_between)

            if avg_days > 7:
                tips.append("You could climb more frequently. Aim for 2-3 sessions per week for optimal improvement.")
            elif avg_days < 1.5:
                tips.append("Remember to allow time for recovery between intense climbing sessions.")

    # If we couldn't generate enough specific tips, add some general ones
    while len(tips) < 3:
        category = random.choice(list(CLIMBING_TIPS.keys()))
        tip = random.choice(CLIMBING_TIPS[category])
        if tip not in tips:
            tips.append(tip)

    return tips


# Add a React front-end component for the dashboard visualization
@app.route('/react_dashboard')
@login_required
def react_dashboard():
    return render_template('react_dashboard.html')


@app.route('/api/user_data')
@login_required
def user_data_api():
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'profile_picture': current_user.profile_picture,
        'location': current_user.location,
        'climbing_since': current_user.climbing_since.strftime('%Y-%m-%d') if current_user.climbing_since else None,
        'favorite_gym': current_user.favorite_gym,
        'experience_years': current_user.climbing_experience_years
    }
    return jsonify(user_data)


@app.route('/api/climbing_stats')
@login_required
def climbing_stats_api():
    # Get recent routes
    recent_routes = Route.query.filter_by(user_id=current_user.id).order_by(Route.date.desc()).limit(10).all()

    routes_data = []
    for route in recent_routes:
        routes_data.append({
            'id': route.id,
            'name': route.name,
            'grade': route.grade,
            'style': route.style,
            'date': route.date.strftime('%Y-%m-%d'),
            'sent': route.sent,
            'attempts': route.attempts,
            'points': GRADE_POINTS.get(route.grade, 0)
        })

    # Get statistics
    total_routes = Route.query.filter_by(user_id=current_user.id).count()
    sent_routes = Route.query.filter_by(user_id=current_user.id, sent=True).count()

    # Get the highest grade
    highest_route = Route.query.filter_by(user_id=current_user.id, sent=True).order_by(desc(Route.grade)).first()
    highest_grade = highest_route.grade if highest_route else "None"

    # Get weekly points
    weekly_points = current_user.get_weekly_points()

    # Get all graph data
    graph_data = generate_stats_api_data(current_user.id)

    return jsonify({
        'recent_routes': routes_data,
        'stats': {
            'total_routes': total_routes,
            'sent_routes': sent_routes,
            'highest_grade': highest_grade,
            'weekly_points': weekly_points
        },
        'graphs': graph_data
    })


def generate_stats_api_data(user_id):
    """Generate raw data for React visualizations"""
    # Get routes for analysis
    routes = Route.query.filter_by(user_id=user_id).all()

    if not routes:
        return {}

    # Convert to DataFrame
    data = []
    for route in routes:
        data.append({
            'date': route.date,
            'grade': route.grade,
            'points': GRADE_POINTS.get(route.grade, 0),
            'sent': route.sent,
            'style': route.style,
            'personal_difficulty': route.personal_difficulty,
            'attempts': route.attempts,
            'hold_types': route.hold_types,
            'location': route.location
        })

    df = pd.DataFrame(data)

    result = {}

    # Grade distribution
    if not df.empty:
        grade_counts = df[df['sent'] == True].groupby('grade').size().reset_index(name='count')

        # Sort grades properly
        grade_order = sorted(list(GRADE_POINTS.keys()), key=lambda x: GRADE_POINTS[x])
        grade_counts['grade'] = pd.Categorical(grade_counts['grade'], categories=grade_order, ordered=True)
        grade_counts = grade_counts.sort_values('grade')

        result['grade_distribution'] = grade_counts.to_dict(orient='records')

    # Weekly progress
    if not df.empty:
        df['week'] = df['date'].dt.strftime('%Y-%U')
        weekly_progress = df.groupby('week').agg(
            total_points=('points', 'sum'),
            count=('grade', 'count')
        ).reset_index()

        result['weekly_progress'] = weekly_progress.to_dict(orient='records')

    # Style performance
    if not df.empty and 'style' in df.columns:
        style_performance = df[df['sent'] == True].groupby('style').agg(
            avg_grade_points=('points', 'mean'),
            count=('style', 'count')
        ).reset_index()

        result['style_performance'] = style_performance.to_dict(orient='records')

    # Location performance
    if not df.empty and 'location' in df.columns:
        location_performance = df.groupby('location').agg(
            avg_grade_points=('points', 'mean'),
            count=('location', 'count')
        ).reset_index()

        result['location_performance'] = location_performance.to_dict(orient='records')

    return result


@app.route('/api/friends_data')
@login_required
def friends_data_api():
    # Get friends list
    friends_data = []
    friendships = Friendship.query.filter_by(user_id=current_user.id, status='accepted').all()

    for friendship in friendships:
        friend = User.query.get(friendship.friend_id)

        if friend:
            # Get weekly points
            weekly_points = friend.get_weekly_points()

            # Get most recent sent route
            recent_route = Route.query.filter_by(user_id=friend.id, sent=True).order_by(
                Route.date.desc()).first()

            friends_data.append({
                'id': friend.id,
                'username': friend.username,
                'profile_picture': friend.profile_picture,
                'weekly_points': weekly_points,
                'recent_grade': recent_route.grade if recent_route else None,
                'recent_route_name': recent_route.name if recent_route else None,
                'recent_date': recent_route.date.strftime('%Y-%m-%d') if recent_route else None
            })

    # Add current user data for comparison
    my_weekly_points = current_user.get_weekly_points()
    my_recent_route = Route.query.filter_by(user_id=current_user.id, sent=True).order_by(
        Route.date.desc()).first()

    user_data = {
        'id': current_user.id,
        'username': current_user.username + " (You)",
        'profile_picture': current_user.profile_picture,
        'weekly_points': my_weekly_points,
        'recent_grade': my_recent_route.grade if my_recent_route else None,
        'recent_route_name': my_recent_route.name if my_recent_route else None,
        'recent_date': my_recent_route.date.strftime('%Y-%m-%d') if my_recent_route else None
    }

    friends_data.append(user_data)

    # Sort by weekly points for leaderboard
    friends_data.sort(key=lambda x: x['weekly_points'], reverse=True)

    return jsonify(friends_data)


# Template for the HTML and CSS of our application
@app.route('/static/styles.css')
def styles():
    return """
    /* ClimbOn Styles */
    :root {
        --primary: #FF5733;
        --primary-dark: #CC4527;
        --secondary: #3498DB;
        --secondary-dark: #2980B9;
        --dark: #282C34;
        --light: #F5F5F5;
        --gray: #95A5A6;
        --success: #2ECC71;
        --warning: #F39C12;
        --danger: #E74C3C;
        --text: #333333;
    }

    body {
        font-family: 'Roboto', sans-serif;
        background-color: var(--light);
        color: var(--text);
        margin: 0;
        padding: 0;
        min-height: 100vh;
        display: flex;
        flex-direction: column;
    }

    .navbar {
        background-color: var(--dark);
        color: white;
        padding: 1rem 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }

    .navbar-brand {
        font-family: 'Montserrat', sans-serif;
        font-size: 1.8rem;
        font-weight: 700;
        color: var(--primary);
        text-decoration: none;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .navbar-nav {
        display: flex;
        gap: 1.5rem;
        align-items: center;
    }

    .nav-link {
        color: white;
        text-decoration: none;
        font-weight: 500;
        transition: color 0.2s ease;
    }

    .nav-link:hover {
        color: var(--primary);
    }

    .active {
        color: var(--primary);
        border-bottom: 2px solid var(--primary);
    }

    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 2rem;
        flex: 1;
    }

    .card {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(0,0,0,0.1);
        padding-bottom: 1rem;
        margin-bottom: 1rem;
    }

    .card-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--dark);
        margin: 0;
    }

    .btn {
        display: inline-block;
        font-weight: 500;
        text-align: center;
        white-space: nowrap;
        vertical-align: middle;
        user-select: none;
        border: 1px solid transparent;
        padding: 0.5rem 1rem;
        font-size: 1rem;
        line-height: 1.5;
        border-radius: 4px;
        transition: all 0.2s ease-in-out;
        cursor: pointer;
        text-decoration: none;
    }

    .btn-primary {
        background-color: var(--primary);
        color: white;
        border-color: var(--primary);
    }

    .btn-primary:hover {
        background-color: var(--primary-dark);
        border-color: var(--primary-dark);
    }

    .btn-secondary {
        background-color: var(--secondary);
        color: white;
        border-color: var(--secondary);
    }

    .btn-secondary:hover {
        background-color: var(--secondary-dark);
        border-color: var(--secondary-dark);
    }

    .btn-outline {
        background-color: transparent;
        color: var(--primary);
        border-color: var(--primary);
    }

    .btn-outline:hover {
        background-color: var(--primary);
        color: white;
    }

    .form-group {
        margin-bottom: 1rem;
    }

    .form-label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: 500;
    }

    .form-control {
        display: block;
        width: 100%;
        padding: 0.5rem 0.75rem;
        font-size: 1rem;
        line-height: 1.5;
        color: var(--text);
        background-color: white;
        background-clip: padding-box;
        border: 1px solid var(--gray);
        border-radius: 4px;
        transition: border-color 0.15s ease-in-out;
    }

    .form-control:focus {
        border-color: var(--primary);
        outline: 0;
        box-shadow: 0 0 0 0.2rem rgba(255, 87, 51, 0.25);
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 1rem;
    }

    .stat-card {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        padding: 1.5rem;
        text-align: center;
        transition: transform 0.3s ease;
    }

    .stat-card:hover {
        transform: translateY(-5px);
    }

    .stat-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--primary);
        margin: 0.5rem 0;
    }

    .stat-label {
        font-size: 1rem;
        color: var(--gray);
        margin-bottom: 0;
    }

    .route-card {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem;
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }

    .route-card:hover {
        transform: translateX(5px);
    }

    .route-grade {
        font-size: 1.5rem;
        font-weight: 700;
        color: white;
        background-color: var(--primary);
        width: 60px;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .route-info {
        flex-grow: 1;
    }

    .route-name {
        font-size: 1.2rem;
        font-weight: 600;
        margin: 0 0 0.25rem;
    }

    .route-details {
        display: flex;
        gap: 1rem;
        font-size: 0.9rem;
        color: var(--gray);
    }

    .route-actions {
        display: flex;

"""


if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()

    # Run the Flask development server
    app.run(debug=True)

