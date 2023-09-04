from flask import Flask, flash, request, render_template, redirect, url_for, session, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.app_context().push()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bug_busters.db'
app.config['SECRET_KEY'] = 'bug_busters'
db = SQLAlchemy(app)


login_manager = LoginManager()
login_manager.login_view = 'login'  # Set the login view route
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # Load a user object by their user ID
    return User.query.get(int(user_id))
# Define your database models (corresponding to your schema)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_student = db.Column(db.Boolean, default=False)
    is_faculty = db.Column(db.Boolean, default=False)
    student_info = db.relationship('Student', back_populates='user')

    # Add other user-related fields (e.g., name, email, etc.)

class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    user = db.relationship('User', backref='faculty_info')
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    taught_classes = db.Column(db.String(50), nullable=False)

class Class(db.Model):
    batch = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('faculty.id'))

# Define an association table for the many-to-many relationship
student_classes = db.Table(
    'student_classes',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id')),
    db.Column('class_id', db.Integer, db.ForeignKey('class.batch'))
)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    user = db.relationship('User', backref='student_info')
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    user = db.relationship('User', back_populates='student_info')

    # Add a many-to-many relationship to represent classes registered by students
    registered_classes = db.relationship('Class', secondary=student_classes, backref='registered_students')

# Attendance model to track student attendance
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    student = db.relationship('Student', backref='attendance')
    class_id = db.Column(db.Integer, db.ForeignKey('class.batch'))
    class_info = db.relationship('Class', backref='attendance_records')
    status = db.Column(db.String(10))  # You can use 'P' for present and 'A' for absent

class LeaveApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
# Summary Model (to store attendance summary data)
class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.batch'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    attendance_percentage = db.Column(db.Float, nullable=False)

db.create_all()

def get_classes_from_database():
    # Query the database to retrieve classes
    classes = Class.query.all()

    # Convert the classes to a list of dictionaries with 'value' and 'label' keys
    class_list = [{'value': class_obj.batch, 'label': class_obj.class_name} for class_obj in classes]

    return class_list



@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            if user.is_student == 1:
                return redirect(url_for('student_dashboard'))  # Redirect to the student dashboard for students
            else:
                return redirect(url_for('faculty_dashboard'))  # Redirect to the admin dashboard for others (assuming an admin_dashboard route exists)
        else:
            pass

    # If the request method is GET or login is unsuccessful, render the login page
    return render_template('login.html')

@app.route('/student_dashboard', methods=['GET', 'POST'])
@login_required  # Use the @login_required decorator to ensure the user is logged in
def student_dashboard():
    class_options = get_classes_from_database()  # Replace with your data retrieval logic

    if request.method == 'POST':
        selected_class = request.form.get('subject')  # Assuming you have a form field named 'subject'
        # Query the database to retrieve attendance data for the selected class
        attendance_data = Attendance.query.filter_by(student_id=current_user.student_info.id, class_id=selected_class).all()

        if attendance_data:
            # Render the template with attendance data
            return render_template('student_dashboard.html', attendance_data=attendance_data, selected_class=selected_class)
        else:
            flash('No attendance data found for the selected class.', 'warning')

    # If it's a GET request or no attendance data was found, render the template without data
    return render_template('student_dashboard.html', class_options=class_options)


@app.route('/student/apply_leave', methods=['GET', 'POST'])
@login_required
def apply_leave():
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        # Save the leave application to the database
        leave_application = LeaveApplication(
            student_id=current_user.student_info.id,
            start_date=start_date,
            end_date=end_date,
            status='Pending'
        )
        db.session.add(leave_application)
        db.session.commit()
        return redirect(url_for('student_dashboard'))
    return render_template('apply_leave.html')

# List Leave Applications (Faculty)
@app.route('/faculty/leave_applications')
@login_required
def faculty_leave_applications():
    if not current_user.is_faculty:
        return redirect(url_for('dashboard'))

    # Retrieve leave applications submitted by students for faculty approval
    leave_applications = LeaveApplication.query.filter_by(status='Pending').all()
    return render_template('faculty_leave_applications.html', leave_applications=leave_applications)

@app.route('/faculty/dashboard')
@login_required
def faculty_dashboard():
    if current_user.is_faculty:
        # If the user is a faculty member, retrieve faculty-specific data
        faculty_classes = Class.query.filter_by(instructor_id=current_user.id).all()
        return render_template('admin_dashboard.html', class_options=faculty_classes, is_admin=True)
    return redirect(url_for('student_dashboard'))

@app.route('/subjects.html', methods=['GET'])
def subjects():
    class_options=get_classes_from_database()
    return render_template('subjects.html', class_options=class_options)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
