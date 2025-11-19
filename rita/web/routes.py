from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from database.db import access_db
from services.peter_client import lookup_staff_by_details  # we'll sketch this
from services.auth import login_required, is_email_allowed

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/', methods=['GET'])
def index():
    """
    Entry point for Rita.

    - If user is already authenticated with work Google -> go to My Access.
    - Otherwise show the "Do you have a work Google account?" choice.
    """
    if current_user.is_authenticated:
        return redirect(url_for('web.my_access'))

    return render_template('landing.html')   # choice screen


@web_bp.route('/my-access', methods=['GET'])
@login_required
def my_access():
    """
    Authenticated staff view:
    - Use Peter to get their current access and render a dashboard.
    """
    # We'll later call Peter here using their work email.
    # For now you can stub this.
    # Example:
    # staff_info = peter_client.get_staff_by_email(current_user.email)
    staff_info = {}  # TODO

    return render_template('my_access.html', user=current_user, staff_info=staff_info)


@web_bp.route('/no-work-google', methods=['GET'])
def no_work_google_form():
    """
    Path for staff who DON'T have a work Google account.
    They identify themselves by name + email so we can match them via Peter.
    """
    return render_template('no_work_google.html')


@web_bp.route('/no-work-google', methods=['POST'])
def no_work_google_submit():
    """
    Handle form submission for people without a work Google account.
    """
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip().lower()

    if not first_name or not last_name or not email:
        flash('First name, last name and email are required.', 'error')
        return redirect(url_for('web.no_work_google_form'))

    # Ask Peter if we know this person
    match = lookup_staff_by_details(
        email=email,
        first_name=first_name,
        last_name=last_name,
    )

    # A few possible outcomes:

    if not match:
        # No record in Peter at all – treat as "unverified" / HR follow-up.
        # For now, create a generic access request record for all-staff emails,
        # flagged as unverified.
        result = staff_db.submit_access_request(
            name=f"{first_name} {last_name}",
            email=email,
            phone=None,
            reason="Requested all-staff emails (no work Google; not found in staff DB)",
        )
        # You could set an extra flag/field in the DB for "unverified" if you want.
        return render_template(
            'request_submitted.html',
            name=f"{first_name} {last_name}",
            email=email,
            note="We couldn't find you in our staff records; HR/IT will review this."
        )

    if match['status'] != 'active':
        flash("We found your record, but you're not currently listed as active staff. "
              "Please contact HR if you think this is an error.", 'error')
        return redirect(url_for('web.no_work_google_form'))

    if match.get('has_google_account'):
        # In your world: if they have a work Google account, they auto-get all-staff.
        # This is probably someone whose Google account exists but they don't realise, or something odd.
        return render_template(
            'request_submitted.html',
            name=f"{first_name} {last_name}",
            email=email,
            note=("Our records show you have a work Google account. "
                  "All staff with a work Google account are automatically on the "
                  "all-staff mailing list. If you're not receiving emails, please contact IT.")
        )

    # Normal case: known active staff, no work Google account.
    # This is your exact "add their personal email to all-staff" use case.

    result = staff_db.submit_access_request(
        name=f"{first_name} {last_name}",
        email=email,
        phone=None,
        reason="Request to receive all-staff emails (no work Google account)",
    )

    if 'error' in result:
        flash(result['error'], 'error')
        return redirect(url_for('web.no_work_google_form'))

    return render_template(
        'request_submitted.html',
        name=f"{first_name} {last_name}",
        email=email,
        note="We'll review your request and, if appropriate, add this email to all-staff."
    )
