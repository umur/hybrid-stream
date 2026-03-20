from hea.operator_registry import register
from .risk       import RiskCheck
from .anomaly    import AnomalyDetector
from .stat_agg   import StatAggregator
from .compliance import ComplianceLogger


def register_w3_operators():
    register("RiskCheck",       RiskCheck)
    register("AnomalyDetector", AnomalyDetector)
    register("StatAggregator",  StatAggregator)
    register("ComplianceLogger", ComplianceLogger)


def build_w3_pipeline(engine) -> list:
    """
    W3 DAG: 30 operators, 500k ev/s financial stream.
    """
    pipeline = []

    for category in RiskCheck.CATEGORIES:
        op = RiskCheck(operator_id=f"risk-{category}", risk_category=category)
        pipeline.append((op, ["w3-trades"], [f"w3-risk-{category}"]))

    for mc in ["price_deviation", "volume_spike", "spread_anomaly", "order_flow_imbalance"]:
        op = AnomalyDetector(operator_id=f"anomaly-{mc}", metric_class=mc)
        pipeline.append((op, ["w3-trades"], [f"w3-anomaly-{mc}"]))

    instruments = [
        "equities", "bonds", "fx", "commodities", "derivatives", "etfs",
        "options", "futures", "swaps", "indices", "crypto", "structured_products"
    ]
    for instr in instruments:
        op = StatAggregator(operator_id=f"stat-{instr}", instrument_class=instr)
        pipeline.append((op, ["w3-trades"], [f"w3-stats-{instr}"]))

    for domain in ComplianceLogger.DOMAINS:
        op = ComplianceLogger(operator_id=f"compliance-{domain}", compliance_domain=domain)
        pipeline.append((op, ["w3-trades"], [f"w3-compliance-{domain}"]))

    return pipeline
