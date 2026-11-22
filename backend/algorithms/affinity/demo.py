"""Deterministic demonstration weights; does not read future observations."""


def profile_weights(count: int, profile: list[float]) -> list[float]:
    weights = []
    for index in range(count):
        if index < len(profile):
            weights.append(profile[index])
        else:
            weights.append(profile[-1] * 0.65 ** (index - len(profile) + 1))
    return weights
