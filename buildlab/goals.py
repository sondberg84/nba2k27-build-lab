"""Build goals and the attribute floors they imply.

Every badge and animation requirement in the data is a lower bound, so a goal
converts to a set of attribute floors. A goal whose requirement uses OR
converts to several alternative floor sets, and the solver picks the cheapest.
"""

from buildlab import animations, badges, reference


class Goal:
    """Base class. Subclasses return a list of alternative floor dicts.

    An empty list means the goal is impossible at that height — not that it is
    free. Callers must distinguish those.
    """

    def floor_options(self, height_inches):
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError


class AttributeGoal(Goal):
    """A bare attribute floor, e.g. three_point at least 90."""

    def __init__(self, attribute, minimum):
        self.attribute = attribute
        self.minimum = minimum

    def floor_options(self, height_inches):
        names = reference.attribute_names()
        if self.attribute not in names:
            raise KeyError(
                f"no builder attribute named {self.attribute!r}; "
                f"valid names are {names}"
            )
        return [{self.attribute: self.minimum}]

    def describe(self):
        return f"{self.attribute} >= {self.minimum}"


class BadgeGoal(Goal):
    """A badge at a tier."""

    def __init__(self, badge_name, tier):
        self.badge_name = badge_name
        self.tier = tier

    def floor_options(self, height_inches):
        if self.tier not in badges.TIERS:
            raise ValueError(
                f"{self.tier!r} is not a tier that attributes can reach; "
                f"valid tiers are {badges.TIERS}. Legend is not purchasable at "
                "build creation and has no attribute requirements."
            )
        badge = badges.by_name(self.badge_name)
        if not badges.height_eligible(badge["badge"], height_inches):
            return []
        requirements = badges.requirements_for(badge["badge"], self.tier)
        if len(requirements) == 1:
            entry = requirements[0]
            return [{entry["name"]: entry["minimum"]}]
        first, second = requirements
        if first["operator_to_next"] == "OR":
            return [
                {first["name"]: first["minimum"]},
                {second["name"]: second["minimum"]},
            ]
        return [
            {
                first["name"]: first["minimum"],
                second["name"]: second["minimum"],
            }
        ]

    def describe(self):
        return f"{self.badge_name} {self.tier}"


class AnimationGoal(Goal):
    """An animation package, gated by reachability rather than the stated range."""

    def __init__(self, name, family):
        self.name = name
        self.family = family

    def floor_options(self, height_inches):
        row = animations.by_name(self.name, self.family)
        if not animations.reachable_at(self.name, self.family, height_inches):
            return []
        return [dict(row["requirements"])]

    def describe(self):
        return f"{self.family}: {self.name}"
