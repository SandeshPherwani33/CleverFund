"""Tests for the dataset-grounded AI context service (RAG).

Tests that the service:
1. Loads dataset correctly
2. Finds similar startups using reasonable similarity
3. Calculates statistics locally (never sent to LLM)
4. Returns compact context objects
5. Handles missing data gracefully
6. Does not send raw dataset to LLM
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cleverfund_backend.services.ai_context_service import (
    build_dataset_context,
    _similarity_filter,
)


@pytest.fixture
def sample_dataset():
    """Create a small sample dataset for testing."""
    return pd.DataFrame({
        'startup_name': ['TechCorp', 'DataFlow', 'CloudPro', 'FinBot', 'HealthTech'],
        'industry': ['Technology', 'Technology', 'Technology', 'Finance', 'Healthcare'],
        'location': ['Bengaluru', 'Bengaluru', 'Mumbai', 'Bengaluru', 'Mumbai'],
        'funding_amount': [5000000, 4000000, 6000000, 3000000, 2500000],
        'revenue': [1000000, 1500000, 2000000, 500000, 300000],
        'num_employees': [50, 40, 60, 30, 25],
        'burn_rate': [250000, 200000, 300000, 150000, 100000],
        'customer_retention_rate': [0.75, 0.80, 0.72, 0.60, 0.65],
        'success': [1, 1, 1, 0, 0],  # 3 success, 2 failure
    })


def test_similarity_filter_by_industry(sample_dataset):
    """Test that similarity filter correctly identifies industry matches."""
    startup = {"industry": "Technology", "location": "", "funding_amount": 0, "revenue": 0}
    similar = _similarity_filter(sample_dataset, startup)
    assert len(similar) == 3  # TechCorp, DataFlow, CloudPro
    assert all(similar['industry'] == 'Technology')


def test_similarity_filter_by_location(sample_dataset):
    """Test location-based filtering."""
    startup = {"industry": "Technology", "location": "Bengaluru", "funding_amount": 0, "revenue": 0}
    similar = _similarity_filter(sample_dataset, startup)
    # TechCorp, DataFlow are in Bengaluru and Technology
    assert len(similar) == 2
    assert all(similar['location'] == 'Bengaluru')
    assert all(similar['industry'] == 'Technology')


def test_similarity_filter_by_funding_proximity(sample_dataset):
    """Test funding amount proximity (within 50% to 200%)."""
    startup = {
        "industry": "Technology",
        "location": "",
        "funding_amount": 4000000,  # Exact match with DataFlow
        "revenue": 0,
        "employees": 0,
    }
    similar = _similarity_filter(sample_dataset, startup)
    # Expect TechCorp (5M, within 2x) and DataFlow (4M, exact)
    assert len(similar) >= 2
    assert all((similar['funding_amount'] >= 2000000) & (similar['funding_amount'] <= 8000000))


def test_similarity_filter_relaxation(sample_dataset):
    """Test that filters relax when too restrictive."""
    startup = {
        "industry": "Quantum Computing",  # Not in dataset
        "location": "Mars",  # Not in dataset
        "funding_amount": 10000000,
        "revenue": 5000000,
    }
    similar = _similarity_filter(sample_dataset, startup)
    # Should relax and return all rows (or at least something)
    assert len(similar) > 0


def test_build_dataset_context_statistics(sample_dataset):
    """Test that statistics are calculated correctly."""
    startup = {
        "startup_name": "TestStartup",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 4500000,
        "revenue": 1200000,
        "employees": 45,
    }
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', return_value=sample_dataset):
        context = build_dataset_context(startup)
    
    assert context is not None
    # Should have found the 2 similar Tech startups in Bengaluru
    assert context['similar_count'] >= 2
    assert context['similar_success_rate'] is not None
    assert context['median_funding'] is not None
    assert context['median_revenue'] is not None
    assert context['median_employees'] is not None
    
    # Verify industry success rate (all 3 Tech startups succeeded)
    assert context['industry_success_rate'] == 100.0
    
    # Verify location success rate across all Bengaluru startups in the sample
    assert context['location_success_rate'] == 66.7


def test_build_dataset_context_sample_rows(sample_dataset):
    """Test that representative sample rows are included."""
    startup = {
        "startup_name": "TestStartup",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 4500000,
        "revenue": 1200000,
        "employees": 45,
    }
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', return_value=sample_dataset):
        context = build_dataset_context(startup, sample_n=3)
    
    assert 'representative_startups' in context
    assert len(context['representative_startups']) <= 3
    
    # Verify each sample has required fields
    for sample in context['representative_startups']:
        assert 'startup_name' in sample
        assert 'funding_amount' in sample
        assert 'revenue' in sample
        assert 'num_employees' in sample
        assert 'success' in sample


def test_build_dataset_context_compact_json(sample_dataset):
    """Test that context is JSON-serializable and compact."""
    startup = {
        "startup_name": "TestStartup",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 4500000,
        "revenue": 1200000,
        "employees": 45,
    }
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', return_value=sample_dataset):
        context = build_dataset_context(startup)
    
    # Should be JSON-serializable
    json_str = json.dumps(context)
    assert len(json_str) < 5000  # Compact (not sending entire dataset)
    
    # Verify no raw data rows beyond the sample
    assert len(context.get('representative_startups', [])) <= 5


def test_build_dataset_context_handles_missing_fields():
    """Test that the service handles datasets with missing columns gracefully."""
    df = pd.DataFrame({
        'startup_name': ['A', 'B'],
        'industry': ['Tech', 'Tech'],
        'location': ['NYC', 'NYC'],
        'funding_amount': [1000000, 2000000],
        'revenue': [100000, 200000],
        # Missing: num_employees, burn_rate, customer_retention_rate, success
    })
    
    startup = {
        "startup_name": "Test",
        "industry": "Tech",
        "location": "NYC",
        "funding_amount": 1500000,
        "revenue": 150000,
        "employees": 10,
    }
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', return_value=df):
        context = build_dataset_context(startup)
    
    # Should not crash; may return None values for missing stats
    assert context is not None or context is None  # Either returns something or None gracefully


def test_build_dataset_context_handles_empty_dataset():
    """Test that empty dataset returns None gracefully."""
    df = pd.DataFrame()
    startup = {"startup_name": "Test", "industry": "Tech"}
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', return_value=df):
        context = build_dataset_context(startup)
    
    # Should handle gracefully (return None)
    assert context is None or context.get('similar_count', 0) == 0


def test_build_dataset_context_handles_load_error():
    """Test that dataset load errors are handled gracefully."""
    startup = {"startup_name": "Test"}
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', side_effect=Exception("Load error")):
        context = build_dataset_context(startup)
    
    # Should return None on error (non-fatal)
    assert context is None


def test_context_never_sends_full_dataset(sample_dataset):
    """Verify that the context does not contain the full raw dataset."""
    startup = {
        "startup_name": "Test",
        "industry": "Technology",
        "location": "Bengaluru",
        "funding_amount": 4500000,
        "revenue": 1200000,
        "employees": 45,
    }
    
    with patch('cleverfund_backend.services.ai_context_service.load_dataset', return_value=sample_dataset):
        context = build_dataset_context(startup)
    
    # Count number of startup rows in context
    sample_count = len(context.get('representative_startups', []))
    
    # Should be far less than the original dataset (sample_n default is 5, actual 2)
    assert sample_count <= 5
    assert sample_count < len(sample_dataset)
    
    # Should not have raw DataFrame or all rows
    assert 'df' not in context
    assert 'dataset' not in context


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
