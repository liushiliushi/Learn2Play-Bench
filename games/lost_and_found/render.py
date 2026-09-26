"""Player-facing rendering for Lost & Found Office."""

from __future__ import annotations

from .models import CaseState, EpisodeState, QuestionTopic, ResolutionType


INTRODUCTION = """You manage the Lost & Found Office for one crowded shift.

Three lost items must be handled before closing. Several people may claim the same
item, and accurate details do not always prove ownership: a person may have seen the
item, know its story, or repeat something discussed at the public counter.

Inspect items, question claimants, check limited records, and decide whether to return
or store each item. Wrong returns cause serious disputes, but storing every item also
hurts service quality.

The office closes after 24 turns. A final service score is shown only at the end."""


def trust_label(value: int) -> str:
    if value >= 90:
        return "Steady"
    if value >= 75:
        return "Watchful"
    if value >= 55:
        return "Uneasy"
    return "Strained"


def case_opening(case: CaseState, number: int) -> str:
    people = "\n".join(
        f"- {claimant.display_name} ({claimant.claimant_id}) — {claimant.biography}"
        for claimant in case.claimants.values()
    )
    statements = "\n".join(case.opening_statements)
    return (
        f"CASE {number}/3 — {case.item_name.title()}\n"
        f"On the counter: {case.item_name}, with {case.surface_description}.\n\n"
        f"Claimants:\n{people}\n\nInitial statements, in speaking order:\n{statements}"
    )


def resources_footer(state: EpisodeState) -> str:
    case = state.cases[state.case_index] if state.case_index < len(state.cases) else None
    isolated = "none"
    if case:
        person = next((c for c in case.claimants.values() if c.isolated), None)
        if person:
            isolated = f"{person.display_name} ({person.claimant_id})"
    return (
        f"Turn {state.turn}/{state.max_turns} | Privacy {state.privacy_tokens} | "
        f"Isolation {state.isolation_tokens} | Records {state.record_checks} | "
        f"Trust {trust_label(state.public_trust)} | Isolated: {isolated}"
    )


def status(state: EpisodeState) -> str:
    if state.done:
        return final_report(state)
    case = state.cases[state.case_index]
    public = [case.facts[fid].public_text for fid in sorted(case.public_fact_ids)]
    private = [case.facts[fid].private_text for fid in sorted(case.privately_observed_fact_ids)]
    checked = []
    if case.relevant_record_checked:
        checked.append(case.relevant_record_text)
    if case.decoy_record_checked:
        checked.append(case.decoy_record_text)
    transcript = [
        f"T{record.turn} {case.claimants[record.claimant_id].display_name} "
        f"({record.topic.value}, {'public' if record.public else 'private'}): {record.rendered_text}"
        for record in case.statement_history[-8:]
    ]
    isolated = next((c.display_name for c in case.claimants.values() if c.isolated), "none")
    lines = [
        f"Shift turn: {state.turn} / {state.max_turns}",
        f"Current case: {case.item_name.title()}",
        f"Cases completed: {sum(c.resolved for c in state.cases)} / 3",
        f"Privacy tokens: {state.privacy_tokens}",
        f"Isolation tokens: {state.isolation_tokens}",
        f"Record checks: {state.record_checks}",
        f"Public trust: {trust_label(state.public_trust)}",
        f"Isolated claimant: {isolated}",
        "Publicly exposed details:",
    ]
    lines.extend(f"- {item}" for item in public) if public else lines.append("- none")
    lines.append("Privately observed item notes:")
    lines.extend(f"- {item}" for item in private) if private else lines.append("- none")
    lines.append("Checked records:")
    lines.extend(f"- {item}" for item in checked) if checked else lines.append("- none")
    lines.append("Recent interview log:")
    lines.extend(f"- {item}" for item in transcript) if transcript else lines.append("- none")
    return "\n".join(lines)


def final_report(state: EpisodeState) -> str:
    correct = sum(
        c.resolution_type == ResolutionType.RETURNED and c.selected_recipient_id == c.owner_id
        for c in state.cases
    )
    disputed = sum(
        c.resolution_type == ResolutionType.RETURNED and c.selected_recipient_id != c.owner_id
        for c in state.cases
    )
    stored = sum(c.resolution_type in {ResolutionType.STORED, ResolutionType.FORCED_STORAGE} for c in state.cases)
    outcome_lines = []
    for index, case in enumerate(state.cases, 1):
        if case.resolution_type == ResolutionType.RETURNED and case.selected_recipient_id == case.owner_id:
            text = "No dispute was filed. The recipient later sent a photograph showing the item in regular use before the visit."
        elif case.resolution_type == ResolutionType.RETURNED:
            text = "A later visitor produced a consistent ownership record. The earlier recipient could not be contacted, and the case was marked as disputed."
        elif case.resolution_type == ResolutionType.FORCED_STORAGE:
            text = "The item remained in storage when the office closed."
        else:
            text = "The item remained in storage for a later appointment."
        outcome_lines.append(f"Case {index}, {case.item_name}: {text}")
    return "\n".join(
        [
            "END-OF-SHIFT REPORT",
            *outcome_lines,
            "",
            f"Cases returned without later dispute: {correct}",
            f"Returns later disputed: {disputed}",
            f"Items left in storage: {stored}",
            f"Public trust: {trust_label(state.public_trust)}",
            f"Private interviews remaining: {state.privacy_tokens}",
            f"Final service score: {getattr(state, 'final_score', 0)}",
        ]
    )


def claimant_answer(
    name: str,
    topic: QuestionTopic,
    fact_text: str | None,
    response_kind: str,
    repeated: bool,
    close_wording: bool = False,
) -> str:
    if repeated:
        if fact_text:
            return f'{name} refers back to the earlier answer and repeats the same point: "{fact_text}."'
        return f"{name} says there is nothing more specific to add to the earlier answer."
    if response_kind == "known":
        if topic == QuestionTopic.CONCEALED_DETAIL:
            return f'{name} describes {fact_text} without looking toward the counter.'
        if topic == QuestionTopic.RELATIONSHIP:
            return f"{name} explains that {fact_text}."
        if topic in {QuestionTopic.LOSS_TIMELINE, QuestionTopic.LAST_USE}:
            return f'{name} recalls this sequence: "I {fact_text}."'
        return f"{name} describes the item as having been {fact_text}."
    if response_kind == "heard":
        cue = " The phrasing closely matches words used at the counter earlier." if close_wording else ""
        return f'{name} pauses, then says, "It has {fact_text}."{cue}'
    if response_kind == "scene":
        return f"{name} gives a precise account of finding it {fact_text}, but cannot connect that place to earlier personal use."
    if response_kind == "context":
        return f"{name} knows a related habit: {fact_text}, but cannot supply the exact physical detail."
    if response_kind == "incompatible":
        return f"{name} offers a plausible but uncertain sequence: {fact_text}."
    return f"{name} gives a broad description, then admits to being unsure about that detail."
