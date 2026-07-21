from flask import Blueprint

from app.routes.appointments import bp as appointments_bp
from app.routes.calls import bp as calls_bp
from app.routes.confirmations import bp as confirmations_bp
from app.routes.conversation import bp as conversation_bp
from app.routes.dashboard import bp as dashboard_bp
from app.routes.health import bp as health_bp
from app.routes.patients import bp as patients_bp
from app.routes.protocol import bp as protocol_bp
from app.routes.routing import bp as routing_bp
from app.routes.simulator import bp as simulator_bp
from app.routes.slots import bp as slots_bp
from app.routes.vogent import bp as vogent_bp

api_blueprint = Blueprint("api", __name__)
for blueprint in (
    health_bp,
    patients_bp,
    protocol_bp,
    routing_bp,
    conversation_bp,
    slots_bp,
    confirmations_bp,
    appointments_bp,
    calls_bp,
    dashboard_bp,
    simulator_bp,
    vogent_bp,
):
    api_blueprint.register_blueprint(blueprint)
