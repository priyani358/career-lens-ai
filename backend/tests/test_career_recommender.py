"""Regression tests for the content-based career recommender."""
import unittest

from app.services.career_recommender import rank_careers


CAREERS = [
    {
        "id": "software", "name": "Software Developers", "description": "Design, build, test and maintain software applications.",
        "skills": {"Programming": 3, "Critical Thinking": 2, "SQL": 1}, "tags": ["Technology"],
        "tasks": ["Develop software applications", "Analyze user requirements"],
        "technology_skills": [{"name": "Python"}],
    },
    {
        "id": "analyst", "name": "Data Analysts", "description": "Analyze datasets and build reports for business decisions.",
        "skills": {"Statistics": 3, "SQL": 2, "Data Visualization": 3}, "tags": ["Investigative", "Conventional"],
        "tasks": ["Analyze data and prepare reports"], "technology_skills": [{"name": "Power BI"}],
    },
    {
        "id": "designer", "name": "Web and Digital Interface Designers", "description": "Design digital interfaces and user experiences.",
        "skills": {"Design": 3, "Communication": 2}, "tags": ["Artistic"],
        "tasks": ["Create interface prototypes"], "technology_skills": [{"name": "Figma"}],
    },
]


class CareerRecommenderTests(unittest.TestCase):
    def test_relevant_profile_ranks_software_role_first(self):
        profile = {
            "skills": [{"name": "Programming", "level": 3}, {"name": "Critical Thinking", "level": 2}],
            "interests": ["Web"],
            "goals": "I want to build software applications and APIs",
            "roles": ["Software Developer"],
        }
        ranked = rank_careers(profile, CAREERS, limit=3)
        self.assertEqual(ranked[0]["career"]["id"], "software")
        self.assertGreater(ranked[0]["breakdown"]["skill_coverage"], 0.8)
        self.assertEqual(ranked[0]["breakdown"]["role_fit"], 1.0)

    def test_data_interest_and_profile_skills_rank_analyst(self):
        profile = {
            "skills": [{"name": "Statistics", "level": 3}, {"name": "SQL", "level": 2}],
            "interests": ["Data", "Research"],
            "goals": "Analyze data and explain trends with dashboards",
            "roles": ["Data Analyst"],
        }
        ranked = rank_careers(profile, CAREERS, limit=3)
        self.assertEqual(ranked[0]["career"]["id"], "analyst")

    def test_breakdown_is_bounded_and_reproducible(self):
        profile = {"skills": [], "interests": [], "goals": ""}
        first = rank_careers(profile, CAREERS)
        second = rank_careers(profile, CAREERS)
        self.assertEqual([row["breakdown"] for row in first], [row["breakdown"] for row in second])
        for row in first:
            self.assertGreaterEqual(row["breakdown"]["score"], 0)
            self.assertLessEqual(row["breakdown"]["score"], 1)
            self.assertIn("model", row["breakdown"])

    def test_empty_catalog_returns_no_recommendations(self):
        self.assertEqual(rank_careers({}, [], limit=5), [])


if __name__ == "__main__":
    unittest.main()
