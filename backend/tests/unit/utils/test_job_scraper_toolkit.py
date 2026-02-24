import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from app.utils.toolkit.job_scraper_toolkit import JobScraperToolkit


class FakeJobsDf:
    def __init__(self, records):
        self._records = records
        self.empty = len(records) == 0

    def to_dict(self, orient):
        assert orient == "records"
        return self._records


@pytest.mark.unit
class TestJobScraperToolkit:
    def test_search_jobs_developer_latest_7_days_vancouver_indeed_linkedin_canada(self, monkeypatch):
        records = [
            {
                "job_url": "https://example.com/job/123",
                "title": "Developer",
                "company": "ExampleCo",
                "location": "Vancouver, BC",
                "description": "Backend developer role focusing on Python and FastAPI.",
            }
        ]

        mock_scrape = MagicMock(return_value=FakeJobsDf(records))
        fake_jobspy = types.ModuleType("jobspy")
        fake_jobspy.scrape_jobs = mock_scrape
        monkeypatch.setitem(sys.modules, "jobspy", fake_jobspy)

        with patch.object(JobScraperToolkit, "_load_existing_hashes_sync") as mock_load_hashes:
            mock_load_hashes.return_value = None

            toolkit = JobScraperToolkit(api_task_id="test_task")
            toolkit._known_hashes = set()
            toolkit._hashes_loaded = True

            result = toolkit.search_jobs(
                search_term="developer",
                location="Vancouver",
                site_names=["indeed", "linkedin"],
                country_indeed="Canada",
            )

            data = json.loads(result)

            print([job.get("description") for job in data["jobs"]])

            assert data["status"] == "success"
            assert data["new_jobs"] == 1
            assert data["total_found"] == 1
            assert data["search_criteria"]["search_term"] == "developer"
            assert data["search_criteria"]["location"] == "Vancouver"
            assert data["search_criteria"]["sites"] == ["indeed", "linkedin"]
            assert data["search_criteria"]["hours_old"] == 168
            assert data["search_criteria"]["job_type"] is None

            job = data["jobs"][0]
            assert job["job_url"] == "https://example.com/job/123"
            assert "url_hash" in job

            mock_scrape.assert_called_once()
            _, kwargs = mock_scrape.call_args
            assert kwargs["site_name"] == ["indeed", "linkedin"]
            assert kwargs["search_term"] == "developer"
            assert kwargs["location"] == "Vancouver"
            assert kwargs["hours_old"] == 168
            assert kwargs["country_indeed"] == "Canada"
            assert kwargs["results_wanted"] == 20
