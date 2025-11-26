"""
Web Routes for Nigel
User interface for price monitoring
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from services.auth import login_required
from database.db import db
from services.price_checker import PriceChecker, compare_prices
from config import config
import logging

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Dashboard with monitored quotes and recent activity"""
    try:
        # Get statistics
        stats = db.get_stats()

        # Get recent checks summary
        recent_summary = db.get_recent_checks_summary(hours=24)

        # Get active quotes
        quotes = db.get_all_quotes(active_only=True)

        # Get recent discrepancies
        recent_discrepancies = db.get_discrepancies(resolved=False, limit=5)

        return render_template('index.html',
                               stats=stats,
                               recent_summary=recent_summary,
                               quotes=quotes,
                               recent_discrepancies=recent_discrepancies,
                               user=current_user)

    except Exception as e:
        logger.exception("Error loading dashboard")
        return f"Error loading dashboard: {str(e)}", 500


@web_bp.route('/quotes')
@login_required
def list_quotes():
    """View all monitored quotes"""
    try:
        show_inactive = request.args.get('show_inactive', 'false').lower() == 'true'
        quotes = db.get_all_quotes(active_only=not show_inactive)

        return render_template('quotes.html',
                               quotes=quotes,
                               show_inactive=show_inactive,
                               user=current_user)

    except Exception as e:
        logger.exception("Error listing quotes")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/quotes/add', methods=['GET', 'POST'])
@login_required
def add_quote():
    """Add a new quote to monitor"""
    if request.method == 'POST':
        try:
            quote_id = request.form.get('quote_id', '').strip()
            org = request.form.get('org', '').strip()
            notes = request.form.get('notes', '').strip()

            if not quote_id:
                flash('Quote ID is required', 'error')
                return redirect(url_for('web.add_quote'))

            if not org:
                flash('Organization is required', 'error')
                return redirect(url_for('web.add_quote'))

            # Add to monitoring
            db.add_quote(quote_id, org, notes)
            logger.info(f"Quote {quote_id} added to monitoring by {current_user.email}")

            flash(f'Quote {quote_id} added to monitoring', 'success')
            return redirect(url_for('web.list_quotes'))

        except Exception as e:
            logger.exception("Error adding quote")
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('web.add_quote'))

    return render_template('add_quote.html', user=current_user)


@web_bp.route('/quotes/<quote_id>')
@login_required
def view_quote(quote_id: str):
    """View details for a specific quote"""
    try:
        quote = db.get_quote(quote_id)
        if not quote:
            flash(f'Quote {quote_id} not found', 'error')
            return redirect(url_for('web.list_quotes'))

        # Get price check history for this quote
        history = db.get_price_checks(quote_id=quote_id, limit=50)

        # Get discrepancies for this quote
        discrepancies = db.get_discrepancies(quote_id=quote_id, limit=20)

        return render_template('quote_detail.html',
                               quote=quote,
                               history=history,
                               discrepancies=discrepancies,
                               user=current_user)

    except Exception as e:
        logger.exception(f"Error viewing quote {quote_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.list_quotes'))


@web_bp.route('/quotes/<quote_id>/check', methods=['POST'])
@login_required
def check_quote(quote_id: str):
    """Check the price for a specific quote"""
    try:
        quote = db.get_quote(quote_id)
        if not quote:
            flash(f'Quote {quote_id} not found', 'error')
            return redirect(url_for('web.list_quotes'))

        # Check the price
        checker = PriceChecker()
        result = checker.check_price(quote_id, quote['org'])

        if result['success']:
            current_price = result['price_after']

            # Check for discrepancy
            has_discrepancy = False
            discrepancy_amount = None

            if quote['last_known_price']:
                has_discrepancy, discrepancy_amount = compare_prices(
                    quote['last_known_price'],
                    current_price
                )

                if has_discrepancy:
                    db.create_discrepancy(
                        quote_id=quote_id,
                        org=quote['org'],
                        expected_price=quote['last_known_price'],
                        actual_price=current_price,
                        difference=discrepancy_amount
                    )

            # Update stored price
            db.update_quote_price(quote_id, current_price)

            # Log the check
            db.log_price_check(
                quote_id=quote_id,
                org=quote['org'],
                status='success',
                price_before=result['price_before'],
                price_after=result['price_after'],
                has_discrepancy=has_discrepancy,
                discrepancy_amount=discrepancy_amount,
                banji_response=result['raw_response']
            )

            if has_discrepancy:
                flash(f'Price discrepancy detected! Expected {quote["last_known_price"]}, got {current_price}', 'warning')
            else:
                flash(f'Price check complete: ${current_price}', 'success')
        else:
            db.log_price_check(
                quote_id=quote_id,
                org=quote['org'],
                status='error',
                error_message=result['error']
            )
            db.update_quote_checked(quote_id)
            flash(f'Price check failed: {result["error"]}', 'error')

        return redirect(url_for('web.view_quote', quote_id=quote_id))

    except Exception as e:
        logger.exception(f"Error checking quote {quote_id}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.view_quote', quote_id=quote_id))


@web_bp.route('/quotes/<quote_id>/deactivate', methods=['POST'])
@login_required
def deactivate_quote(quote_id: str):
    """Deactivate monitoring for a quote"""
    try:
        db.deactivate_quote(quote_id)
        logger.info(f"Quote {quote_id} deactivated by {current_user.email}")
        flash(f'Quote {quote_id} monitoring deactivated', 'success')
    except Exception as e:
        logger.exception(f"Error deactivating quote {quote_id}")
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('web.list_quotes'))


@web_bp.route('/quotes/<quote_id>/activate', methods=['POST'])
@login_required
def activate_quote(quote_id: str):
    """Reactivate monitoring for a quote"""
    try:
        db.activate_quote(quote_id)
        logger.info(f"Quote {quote_id} reactivated by {current_user.email}")
        flash(f'Quote {quote_id} monitoring reactivated', 'success')
    except Exception as e:
        logger.exception(f"Error activating quote {quote_id}")
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('web.list_quotes'))


@web_bp.route('/quotes/<quote_id>/delete', methods=['POST'])
@login_required
def delete_quote(quote_id: str):
    """Delete a quote from monitoring"""
    try:
        db.delete_quote(quote_id)
        logger.info(f"Quote {quote_id} deleted by {current_user.email}")
        flash(f'Quote {quote_id} removed from monitoring', 'success')
    except Exception as e:
        logger.exception(f"Error deleting quote {quote_id}")
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('web.list_quotes'))


@web_bp.route('/history')
@login_required
def history():
    """View price check history"""
    try:
        quote_id = request.args.get('quote_id')
        discrepancies_only = request.args.get('discrepancies_only', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 100))

        checks = db.get_price_checks(
            quote_id=quote_id,
            discrepancies_only=discrepancies_only,
            limit=limit
        )

        return render_template('history.html',
                               checks=checks,
                               quote_id=quote_id,
                               discrepancies_only=discrepancies_only,
                               user=current_user)

    except Exception as e:
        logger.exception("Error loading history")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/discrepancies')
@login_required
def discrepancies():
    """View all discrepancies"""
    try:
        show_resolved = request.args.get('show_resolved', 'false').lower() == 'true'

        if show_resolved:
            items = db.get_discrepancies(limit=200)
        else:
            items = db.get_discrepancies(resolved=False, limit=200)

        return render_template('discrepancies.html',
                               discrepancies=items,
                               show_resolved=show_resolved,
                               user=current_user)

    except Exception as e:
        logger.exception("Error loading discrepancies")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))


@web_bp.route('/discrepancies/<int:discrepancy_id>/resolve', methods=['POST'])
@login_required
def resolve_discrepancy(discrepancy_id: int):
    """Mark a discrepancy as resolved"""
    try:
        notes = request.form.get('notes', '')
        db.resolve_discrepancy(
            discrepancy_id=discrepancy_id,
            resolved_by=current_user.email,
            resolution_notes=notes
        )
        logger.info(f"Discrepancy {discrepancy_id} resolved by {current_user.email}")
        flash(f'Discrepancy #{discrepancy_id} marked as resolved', 'success')
    except Exception as e:
        logger.exception(f"Error resolving discrepancy {discrepancy_id}")
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('web.discrepancies'))


@web_bp.route('/check-all', methods=['POST'])
@login_required
def check_all():
    """Check prices for all active quotes"""
    try:
        quotes = db.get_all_quotes(active_only=True)

        if not quotes:
            flash('No active quotes to check', 'warning')
            return redirect(url_for('web.index'))

        checker = PriceChecker()
        results = {'checked': 0, 'discrepancies': 0, 'errors': 0}

        for quote in quotes:
            quote_id = quote['quote_id']
            org = quote['org']

            result = checker.check_price(quote_id, org)

            if result['success']:
                current_price = result['price_after']
                has_discrepancy = False
                discrepancy_amount = None

                if quote['last_known_price']:
                    has_discrepancy, discrepancy_amount = compare_prices(
                        quote['last_known_price'],
                        current_price
                    )

                    if has_discrepancy:
                        db.create_discrepancy(
                            quote_id=quote_id,
                            org=org,
                            expected_price=quote['last_known_price'],
                            actual_price=current_price,
                            difference=discrepancy_amount
                        )
                        results['discrepancies'] += 1

                db.update_quote_price(quote_id, current_price)
                db.log_price_check(
                    quote_id=quote_id,
                    org=org,
                    status='success',
                    price_before=result['price_before'],
                    price_after=result['price_after'],
                    has_discrepancy=has_discrepancy,
                    discrepancy_amount=discrepancy_amount,
                    banji_response=result['raw_response']
                )
                results['checked'] += 1
            else:
                db.log_price_check(
                    quote_id=quote_id,
                    org=org,
                    status='error',
                    error_message=result['error']
                )
                db.update_quote_checked(quote_id)
                results['errors'] += 1

        logger.info(f"Bulk price check by {current_user.email}: {results}")

        if results['discrepancies'] > 0:
            flash(f'Checked {results["checked"]} quotes. Found {results["discrepancies"]} discrepancies!', 'warning')
        elif results['errors'] > 0:
            flash(f'Checked {results["checked"]} quotes with {results["errors"]} errors', 'warning')
        else:
            flash(f'Checked {results["checked"]} quotes. No discrepancies found.', 'success')

        return redirect(url_for('web.index'))

    except Exception as e:
        logger.exception("Error checking all quotes")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('web.index'))
