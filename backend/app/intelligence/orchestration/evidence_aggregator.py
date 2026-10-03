"""
backend/app/intelligence/orchestration/evidence_aggregator.py

Evidence normalization, provenance tracking, and ledger aggregation for Phase 9.2.
Transforms raw specialist agent step outputs into verified, structured EvidenceItem records.
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.intelligence.orchestration.models import (
    EvidenceItem,
    EvidenceType,
    ConfidenceTier,
    PlanStep,
)


class EvidenceAggregator:
    """
    Collects, normalizes, and indexes evidence across specialist agent executions.
    """

    @classmethod
    def aggregate_step_output(
        cls,
        step: PlanStep,
        output: Dict[str, Any],
        existing_ledger: Optional[List[EvidenceItem]] = None,
    ) -> List[EvidenceItem]:
        """
        Extracts structured EvidenceItems from a step's output dictionary.
        """
        new_items: List[EvidenceItem] = []
        agent_id = step.agent_id
        step_id = step.step_id
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Knowledge Agent Output
        if agent_id == "knowledge_agent":
            entities = output.get("entities", [])
            metrics = output.get("metrics", [])
            rules = output.get("rules", [])

            if entities:
                new_items.append(
                    EvidenceItem(
                        evidence_id=f"ev_ent_{uuid.uuid4().hex[:6]}",
                        evidence_type=EvidenceType.BUSINESS_CONTEXT,
                        title=f"Resolved Business Entities ({len(entities)})",
                        summary=f"Identified {len(entities)} verified business entity concepts in data schema.",
                        source_agent=agent_id,
                        step_id=step_id,
                        data_facts={"entities": [e.get("name") for e in entities if isinstance(e, dict)]},
                        confidence=ConfidenceTier.HIGH,
                        created_at=timestamp,
                        lineage=[step_id, "knowledge_store.list_entities"],
                        table_references=[e.get("primary_table") for e in entities if isinstance(e, dict) and e.get("primary_table")],
                    )
                )

            if metrics:
                new_items.append(
                    EvidenceItem(
                        evidence_id=f"ev_met_{uuid.uuid4().hex[:6]}",
                        evidence_type=EvidenceType.METRIC_RESULT,
                        title=f"Verified Metric Semantics ({len(metrics)})",
                        summary=f"Loaded {len(metrics)} verified business metrics.",
                        source_agent=agent_id,
                        step_id=step_id,
                        data_facts={"metrics": [m.get("name") for m in metrics if isinstance(m, dict)]},
                        confidence=ConfidenceTier.HIGH,
                        created_at=timestamp,
                        lineage=[step_id, "knowledge_store.list_metrics"],
                        metric_references=[m.get("name") for m in metrics if isinstance(m, dict) and m.get("name")],
                    )
                )

        # 2. BI Agent Output
        elif agent_id == "bi_agent":
            insights = output.get("insights", [])
            multi_count = output.get("multi_table_count", 0)

            for idx, ins in enumerate(insights[:3]):
                ins_title = ins.get("title", f"Business Insight #{idx+1}") if isinstance(ins, dict) else str(ins)
                ins_summary = ins.get("summary", "") if isinstance(ins, dict) else ""
                tables = ins.get("source_tables", []) if isinstance(ins, dict) else []

                new_items.append(
                    EvidenceItem(
                        evidence_id=f"ev_bi_{uuid.uuid4().hex[:6]}",
                        evidence_type=EvidenceType.TREND if "trend" in ins_title.lower() else EvidenceType.DATABASE_FACT,
                        title=ins_title,
                        summary=ins_summary or "Verified database business insight.",
                        source_agent=agent_id,
                        step_id=step_id,
                        data_facts=ins if isinstance(ins, dict) else {"data": ins},
                        confidence=ConfidenceTier.HIGH,
                        created_at=timestamp,
                        lineage=[step_id, "bi_engine.get_business_insights"],
                        table_references=tables,
                    )
                )

        # 3. Data Analyst Agent Output
        elif agent_id == "data_analyst_agent":
            tables = output.get("discovered_tables", [])
            counts = output.get("table_counts", {})
            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_ana_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.DATABASE_FACT,
                    title=f"Schema & Table Profiles ({len(tables)} tables)",
                    summary=output.get("summary", "Inspected database schema and table distributions."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"tables": tables, "row_counts": counts},
                    confidence=ConfidenceTier.HIGH,
                    created_at=timestamp,
                    lineage=[step_id, "data_analyst_agent.profile"],
                    table_references=tables[:5],
                )
            )

        # 4. Monitoring Agent Output
        elif agent_id == "monitoring_agent":
            health = output.get("system_health", {})
            alerts = output.get("active_alerts", [])
            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_mon_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.ANOMALY if alerts else EvidenceType.DATABASE_FACT,
                    title=f"Continuous Health Status (Score: {health.get('score', 100)})",
                    summary=output.get("summary", "Continuous monitoring status check."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"health": health, "alerts": alerts},
                    confidence=ConfidenceTier.HIGH,
                    created_at=timestamp,
                    lineage=[step_id, "monitoring.monitor_engine"],
                )
            )

        # 5. Investigation Agent Output
        elif agent_id == "investigation_agent":
            hypotheses = output.get("hypotheses", [])
            root_cause = output.get("primary_root_cause", "Analysis pending")
            factors = output.get("contributing_factors", [])

            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_inv_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.INVESTIGATION_FINDING,
                    title=f"Root Cause Finding: {root_cause}",
                    summary=output.get("summary", f"Isolated primary factors: {len(factors)} identified."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"primary_root_cause": root_cause, "hypotheses": hypotheses, "factors": factors},
                    confidence=ConfidenceTier.MODERATE if len(hypotheses) > 1 else ConfidenceTier.HIGH,
                    created_at=timestamp,
                    lineage=[step_id, "investigation_engine.investigate_signal"],
                )
            )

        # 6. Prediction Agent Output
        elif agent_id == "prediction_agent":
            metric = output.get("forecast_metric", "metric")
            trend = output.get("trend_direction", "STABLE")
            projections = output.get("projected_values", [])

            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_prd_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.FORECAST,
                    title=f"Forecast Projection: {metric} ({trend})",
                    summary=output.get("summary", f"Projected future trend for {metric}."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"metric": metric, "trend": trend, "projections": projections},
                    confidence=ConfidenceTier.MODERATE,
                    created_at=timestamp,
                    lineage=[step_id, "predictive.predictor.run_forecast_projection"],
                    metric_references=[metric],
                )
            )

        # 7. Decision Agent Output
        elif agent_id == "decision_agent":
            rec = output.get("recommended_option", "Observation")
            options = output.get("options", [])
            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_dec_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.DECISION_FINDING,
                    title=f"Decision Option: {rec}",
                    summary=output.get("summary", "Evaluated strategic options against evidence ledger."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"recommended": rec, "options": options, "rationale": output.get("rationale")},
                    confidence=ConfidenceTier.HIGH,
                    created_at=timestamp,
                    lineage=[step_id, "decision.decision_engine"],
                )
            )

        # 8. Learning Agent Output
        elif agent_id == "learning_agent":
            recs = output.get("adaptive_recommendations", [])
            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_lrn_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.OUTCOME,
                    title=f"Learned Patterns ({output.get('past_pattern_count', 0)} outcomes)",
                    summary=output.get("summary", "Retrieved historical action outcomes."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"recommendations": recs},
                    confidence=ConfidenceTier.HIGH,
                    created_at=timestamp,
                    lineage=[step_id, "outcome_optimization.adaptive_recommender"],
                )
            )

        # 9. Action Agent Output
        elif agent_id == "action_agent":
            prop = output.get("action_proposal", {})
            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_act_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.ACTION_STATUS,
                    title=f"Proposed Action: {prop.get('title', 'Action Plan')}",
                    summary=output.get("summary", "Drafted action proposal awaiting confirmation."),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts={"proposal": prop, "confirmation_required": True},
                    confidence=ConfidenceTier.HIGH,
                    created_at=timestamp,
                    lineage=[step_id, "actions.action_engine"],
                )
            )

        # Fallback general item if nothing was extracted
        if not new_items and output:
            new_items.append(
                EvidenceItem(
                    evidence_id=f"ev_gen_{uuid.uuid4().hex[:6]}",
                    evidence_type=EvidenceType.DATABASE_FACT,
                    title=f"Step Output: {step.name}",
                    summary=output.get("summary", str(output)[:100]),
                    source_agent=agent_id,
                    step_id=step_id,
                    data_facts=output,
                    confidence=ConfidenceTier.MODERATE,
                    created_at=timestamp,
                    lineage=[step_id],
                )
            )

        return new_items
