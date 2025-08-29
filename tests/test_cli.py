"""
Tests for Context Cleaner CLI interface.
"""

import pytest
import json
import tempfile
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pathlib import Path

from context_cleaner.cli.main import main


class TestContextCleanerCLI:
    """Test suite for Context Cleaner CLI."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
    
    def test_cli_help_command(self):
        """Test CLI help command."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'Context Cleaner' in result.output
        assert 'Advanced productivity tracking' in result.output
    
    def test_cli_version_info(self):
        """Test CLI shows correct commands."""
        result = self.runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert 'start' in result.output
        assert 'dashboard' in result.output
        assert 'analyze' in result.output
        assert 'export' in result.output
        assert 'privacy' in result.output
    
    def test_start_command(self):
        """Test start command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.runner.invoke(main, [
                '--data-dir', temp_dir,
                'start'
            ])
            assert result.exit_code == 0
            assert 'Context Cleaner started' in result.output
    
    def test_start_command_verbose(self):
        """Test start command with verbose output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.runner.invoke(main, [
                '--data-dir', temp_dir,
                '--verbose',
                'start'
            ])
            assert result.exit_code == 0
            assert 'Starting Context Cleaner' in result.output
            assert 'Dashboard available at' in result.output
    
    @patch('context_cleaner.cli.main.ProductivityDashboard')
    def test_dashboard_command(self, mock_dashboard_class):
        """Test dashboard command execution."""
        mock_dashboard = MagicMock()
        mock_dashboard_class.return_value = mock_dashboard
        
        result = self.runner.invoke(main, [
            'dashboard', 
            '--no-browser',
            '--port', '9000'
        ])
        
        # Should attempt to create dashboard
        mock_dashboard_class.assert_called_once()
        mock_dashboard.start_server.assert_called_once_with('localhost', 9000)
    
    @patch('context_cleaner.cli.main._run_productivity_analysis')
    def test_analyze_command_text_output(self, mock_analysis):
        """Test analyze command with text output."""
        # Mock analysis results
        mock_results = {
            "period_days": 7,
            "avg_productivity_score": 85.3,
            "total_sessions": 23,
            "optimization_events": 12,
            "most_productive_day": "Tuesday",
            "recommendations": ["Test recommendation"],
            "analysis_timestamp": "2024-12-20T10:00:00"
        }
        mock_analysis.return_value = mock_results
        
        result = self.runner.invoke(main, [
            'analyze',
            '--days', '7',
            '--format', 'text'
        ])
        
        assert result.exit_code == 0
        assert 'PRODUCTIVITY ANALYSIS REPORT' in result.output
        assert '85.3/100' in result.output
        assert 'Tuesday' in result.output
    
    @patch('context_cleaner.cli.main._run_productivity_analysis')
    def test_analyze_command_json_output(self, mock_analysis):
        """Test analyze command with JSON output."""
        mock_results = {
            "period_days": 7,
            "avg_productivity_score": 85.3,
            "total_sessions": 23
        }
        mock_analysis.return_value = mock_results
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            result = self.runner.invoke(main, [
                'analyze',
                '--days', '7', 
                '--format', 'json',
                '--output', temp_file.name
            ])
            
            assert result.exit_code == 0
            
            # Check JSON output file
            with open(temp_file.name, 'r') as f:
                output_data = json.load(f)
                assert output_data['period_days'] == 7
                assert output_data['avg_productivity_score'] == 85.3
    
    @patch('context_cleaner.cli.main._export_all_data')
    def test_export_command_json(self, mock_export):
        """Test export command with JSON format."""
        mock_data = {
            "export_timestamp": "2024-12-20T10:00:00",
            "sessions": [],
            "metadata": {"total_sessions": 0}
        }
        mock_export.return_value = mock_data
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            result = self.runner.invoke(main, [
                'export',
                '--format', 'json',
                '--output', temp_file.name
            ])
            
            assert result.exit_code == 0
            
            # Verify JSON file was created
            with open(temp_file.name, 'r') as f:
                exported_data = json.load(f)
                assert exported_data['export_timestamp'] == "2024-12-20T10:00:00"
    
    def test_config_show_command(self):
        """Test config show command."""
        result = self.runner.invoke(main, ['config-show'])
        assert result.exit_code == 0
        
        # Should output valid JSON config
        try:
            config_data = json.loads(result.output)
            assert 'dashboard' in config_data
            assert 'tracking' in config_data
            assert 'analysis' in config_data
        except json.JSONDecodeError:
            pytest.fail("config-show output is not valid JSON")
    
    def test_privacy_show_info_command(self):
        """Test privacy show-info command."""
        result = self.runner.invoke(main, ['privacy', 'show-info'])
        assert result.exit_code == 0
        assert 'PRIVACY INFORMATION' in result.output
        assert 'What we track' in result.output
        assert 'Privacy protections' in result.output
    
    @patch('shutil.rmtree')
    def test_privacy_delete_all_command(self, mock_rmtree):
        """Test privacy delete-all command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Confirm deletion when prompted
            result = self.runner.invoke(main, [
                '--data-dir', temp_dir,
                'privacy', 'delete-all'
            ], input='y\n')
            
            assert result.exit_code == 0
            assert 'All data deleted' in result.output
    
    def test_invalid_command_handling(self):
        """Test handling of invalid commands."""
        result = self.runner.invoke(main, ['invalid-command'])
        assert result.exit_code != 0
        assert 'No such command' in result.output
    
    def test_custom_config_file(self):
        """Test CLI with custom configuration file."""
        config_data = {
            "dashboard": {"port": 9999},
            "tracking": {"enabled": False}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as config_file:
            import yaml
            yaml.dump(config_data, config_file)
            config_path = config_file.name
        
        try:
            result = self.runner.invoke(main, [
                '--config', config_path,
                '--verbose',
                'start'
            ])
            assert result.exit_code == 0
            assert '9999' in result.output  # Should use custom port
        finally:
            Path(config_path).unlink()


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""
    
    def setup_method(self):
        """Set up test environment.""" 
        self.runner = CliRunner()
    
    def test_nonexistent_config_file(self):
        """Test handling of nonexistent config file."""
        result = self.runner.invoke(main, [
            '--config', '/nonexistent/config.yaml',
            'start'
        ])
        assert result.exit_code != 0
    
    def test_invalid_data_directory_permissions(self):
        """Test handling of invalid data directory."""
        # Try to use a directory path that should fail
        result = self.runner.invoke(main, [
            '--data-dir', '/root/forbidden',
            'start'
        ])
        # Should either succeed (if permissions allow) or fail gracefully
        assert result.exit_code in [0, 1]
    
    @patch('context_cleaner.cli.main.ProductivityDashboard')
    def test_dashboard_startup_failure(self, mock_dashboard_class):
        """Test dashboard startup failure handling."""
        mock_dashboard = MagicMock()
        mock_dashboard.start_server.side_effect = Exception("Port already in use")
        mock_dashboard_class.return_value = mock_dashboard
        
        result = self.runner.invoke(main, [
            'dashboard',
            '--no-browser'
        ])
        assert result.exit_code == 1
        assert 'Failed to start dashboard' in result.output