import numpy as np

from h01_simulator.config import PolicyConfig, SimConfig
from h01_simulator.model import Propositions, SignalModel
from h01_simulator.policies import POLICIES, constant_revisit_policy, hard_gate_policy, thompson_policy


def _fresh_model(n: int = 4, seed: int = 0) -> SignalModel:
    cfg = SimConfig(n_propositions=n, budget=100, p_pos=0.8, p_neg=0.2, prior_true=0.5)
    props = Propositions(
        truth=np.zeros(n, dtype=np.int8),
        bias_mask=np.zeros(n, dtype=np.int8),
        bias_offsets=np.zeros(n, dtype=np.float64),
    )
    return SignalModel(props, cfg, np.random.default_rng(seed))


def test_hard_gate_warmup_is_round_robin():
    policy = hard_gate_policy(PolicyConfig(kind="hard_gate", warmup_actions=2))
    m = _fresh_model(n=3)
    rng = np.random.default_rng(0)
    picks = [policy(m, i, rng) for i in range(6)]
    assert picks == [0, 1, 2, 0, 1, 2]


def test_hard_gate_excludes_below_threshold():
    policy = hard_gate_policy(PolicyConfig(kind="hard_gate", warmup_actions=1, gate_threshold=0.5))
    m = _fresh_model(n=3)
    for _ in range(10):
        m.observe(0, 0)  # prop 0 -> well below 0.5
    for _ in range(10):
        m.observe(2, 1)  # prop 2 -> well above 0.5
    rng = np.random.default_rng(0)
    picks = [policy(m, 100, rng) for _ in range(400)]
    assert 0 not in picks
    assert set(picks) <= {1, 2}


def test_hard_gate_falls_back_when_all_gated():
    policy = hard_gate_policy(PolicyConfig(kind="hard_gate", warmup_actions=1, gate_threshold=0.99))
    m = _fresh_model(n=3)
    rng = np.random.default_rng(0)
    pick = policy(m, 100, rng)
    assert pick in {0, 1, 2}


def test_policies_dispatch_includes_hard_gate():
    assert "hard_gate" in POLICIES


def test_constant_revisit_zero_prob_matches_hard_gate():
    cfg = PolicyConfig(
        kind="constant_revisit",
        warmup_actions=1,
        gate_threshold=0.5,
        revisit_prob=0.0,
    )
    policy = constant_revisit_policy(cfg)
    m = _fresh_model(n=3)
    for _ in range(10):
        m.observe(0, 0)
    for _ in range(10):
        m.observe(2, 1)
    rng = np.random.default_rng(0)
    picks = [policy(m, 100, rng) for _ in range(400)]
    assert 0 not in picks


def test_constant_revisit_samples_gated_with_given_frequency():
    cfg = PolicyConfig(
        kind="constant_revisit",
        warmup_actions=1,
        gate_threshold=0.5,
        revisit_prob=0.4,
    )
    policy = constant_revisit_policy(cfg)
    m = _fresh_model(n=3)
    for _ in range(10):
        m.observe(0, 0)
    for _ in range(10):
        m.observe(2, 1)
    rng = np.random.default_rng(0)
    picks = np.array([policy(m, 100, rng) for _ in range(4000)])
    gated_rate = (picks == 0).mean()
    assert 0.35 <= gated_rate <= 0.45


def test_constant_revisit_dispatch_registered():
    assert "constant_revisit" in POLICIES


def test_thompson_warmup_is_round_robin():
    policy = thompson_policy(PolicyConfig(kind="thompson", warmup_actions=1))
    m = _fresh_model(n=3)
    rng = np.random.default_rng(0)
    picks = [policy(m, i, rng) for i in range(3)]
    assert picks == [0, 1, 2]


def test_thompson_output_is_a_valid_index_and_tracks_posterior():
    policy = thompson_policy(PolicyConfig(kind="thompson", warmup_actions=1))
    m = _fresh_model(n=5)
    rng = np.random.default_rng(0)

    # Sanity: all picks are valid indices before any observations.
    for _ in range(100):
        pick = policy(m, 1000, rng)
        assert 0 <= pick < 5

    # Drive prop 2's posterior strongly positive.
    for _ in range(40):
        m.observe(2, 1)

    # Over many draws, prop 2 should dominate (chance would be 1/5 = 0.2).
    picks = np.array([policy(m, 1000, rng) for _ in range(2000)])
    assert (picks == 2).mean() > 0.7


def test_thompson_dispatch_registered():
    assert "thompson" in POLICIES


def test_ucb_warmup_covers_all_arms():
    """UCB warmup round-robins through all arms before entering UCB selection."""
    from h01_simulator.config import PolicyConfig, SimConfig
    from h01_simulator.model import SignalModel, generate_propositions
    from h01_simulator.policies import POLICIES

    sim = SimConfig(n_propositions=3, budget=10, p_pos=0.9, p_neg=0.1, prior_true=0.5, seed=42)
    rng = np.random.default_rng(0)
    props = generate_propositions(sim, rng)
    model = SignalModel(props, sim, rng)
    pol = PolicyConfig(kind="ucb", warmup_actions=1, gate_threshold=0.5, ucb_c=1.0)
    fn = POLICIES["ucb"](pol)
    pulls = [fn(model, t, rng) for t in range(3)]
    assert set(pulls) == {0, 1, 2}, f"UCB warmup did not cover all arms: {pulls}"


def test_ucb_policy_balances_pulls_via_internal_tracking():
    """Without any model.observe() calls, posterior_mean stays constant, so the UCB
    score is driven entirely by the closure's internal pull counter. That means UCB
    must round-robin through arms (pulling the under-pulled arm each step) purely
    on the strength of pulls[i] += 1. If the increment were missing, the same arm
    would be picked repeatedly."""
    from h01_simulator.config import PolicyConfig, SimConfig
    from h01_simulator.model import SignalModel, generate_propositions
    from h01_simulator.policies import POLICIES

    sim = SimConfig(n_propositions=2, budget=100, p_pos=0.9, p_neg=0.1, prior_true=0.5, seed=0)
    rng = np.random.default_rng(0)
    props = generate_propositions(sim, rng)
    model = SignalModel(props, sim, rng)
    pol = PolicyConfig(kind="ucb", warmup_actions=1, gate_threshold=0.5, ucb_c=1.0)
    fn = POLICIES["ucb"](pol)

    # Drive 12 calls: 2 warmup + 10 post-warmup. Do NOT call model.observe() so the
    # posterior_mean stays uniform across arms. Any spread in choices must come from
    # the closure's pulls[i] += 1 tracking.
    choices = [fn(model, t, rng) for t in range(12)]

    # Warmup must cover both arms.
    assert set(choices[:2]) == {0, 1}

    # Post-warmup: with uniform posteriors and closure-tracked pulls, UCB alternates
    # (pulls the less-pulled arm each step). Over 10 post-warmup calls the two arms
    # should be selected within 1 of each other.
    post_warmup = choices[2:]
    count_0 = post_warmup.count(0)
    count_1 = post_warmup.count(1)
    assert abs(count_0 - count_1) <= 1, (
        f"UCB is not tracking pulls incrementally — arms got {count_0} vs {count_1} "
        f"selections. Expected near-balance under uniform posteriors."
    )
