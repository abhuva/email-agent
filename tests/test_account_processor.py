"""
Tests for AccountProcessor class.

This test suite verifies:
- State isolation between AccountProcessor instances
- Proper setup/run/teardown lifecycle
- Pipeline execution (blacklist, parse, LLM, whitelist, note generation)
- Error handling and resource cleanup
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any, List

from src.account_processor import (
    AccountProcessor,
    AccountProcessorError,
    AccountProcessorSetupError,
    AccountProcessorRunError,
    ConfigurableImapClient,
    create_imap_client_from_config,
    estimate_processing_cost,
    prompt_user_confirmation,
    CostEstimate
)
from src.models import EmailContext, from_imap_dict
from src.rules import ActionEnum
from src.llm_client import LLMResponse
from src.decision_logic import ClassificationResult, ClassificationStatus


@pytest.fixture
def sample_account_config():
    """Sample account configuration for testing."""
    return {
        'imap': {
            'server': 'imap.test.com',
            'port': 993,
            'username': 'test@example.com',
            'password_env': 'TEST_IMAP_PASSWORD',
            'query': 'ALL',
            'processed_tag': 'AIProcessed'
        },
        'auth': {
            'method': 'password',
            'password_env': 'TEST_IMAP_PASSWORD'
        },
        'processing': {
            'max_emails_per_run': 10
        }
    }


@pytest.fixture
def mock_imap_client():
    """Mock IMAP client for testing."""
    client = Mock()
    client._connected = False
    client.connect = Mock()
    client.disconnect = Mock()
    client.count_unprocessed_emails = Mock(return_value=(0, []))
    client.get_unprocessed_emails = Mock(return_value=[])
    client.get_email_by_uid = Mock()
    client.set_flag = Mock(return_value=True)
    return client


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = Mock()
    client.classify_email = Mock(return_value=LLMResponse(
        spam_score=2,
        importance_score=8,
        raw_response='{"spam_score": 2, "importance_score": 8}'
    ))
    return client


@pytest.fixture
def mock_note_generator():
    """Mock note generator for testing."""
    generator = Mock()
    generator.generate_note = Mock(return_value="# Test Note\n\nTest content")
    return generator


@pytest.fixture
def mock_decision_logic():
    """Mock decision logic for testing."""
    logic = Mock()
    result = ClassificationResult(
        is_important=True,
        is_spam=False,
        importance_score=8,
        spam_score=2,
        confidence=0.9,
        status=ClassificationStatus.SUCCESS,
        raw_scores={'spam_score': 2, 'importance_score': 8},
        metadata={}
    )
    logic.classify = Mock(return_value=result)
    return logic


@pytest.fixture
def account_processor(sample_account_config, mock_imap_client, mock_llm_client, 
                     mock_note_generator, mock_decision_logic):
    """Create AccountProcessor instance for testing."""
    from src.rules import load_blacklist_rules, load_whitelist_rules
    from src.content_parser import parse_html_content
    
    def imap_factory(config):
        return mock_imap_client
    
    processor = AccountProcessor(
        account_id='test_account',
        account_config=sample_account_config,
        imap_client_factory=imap_factory,
        llm_client=mock_llm_client,
        blacklist_service=load_blacklist_rules,
        whitelist_service=load_whitelist_rules,
        note_generator=mock_note_generator,
        parser=parse_html_content,
        decision_logic=mock_decision_logic
    )
    return processor


class TestAccountProcessorInitialization:
    """Test AccountProcessor initialization and state isolation."""
    
    def test_initialization(self, account_processor, sample_account_config):
        """Test that AccountProcessor initializes correctly."""
        assert account_processor.account_id == 'test_account'
        assert account_processor.config == sample_account_config
        assert account_processor._imap_conn is None
        assert account_processor._processing_context == {}
        assert len(account_processor._processed_emails) == 0
    
    def test_state_isolation_between_instances(self, sample_account_config, 
                                               mock_imap_client, mock_llm_client,
                                               mock_note_generator, mock_decision_logic):
        """Test that different AccountProcessor instances have isolated state."""
        from src.rules import load_blacklist_rules, load_whitelist_rules
        from src.content_parser import parse_html_content
        
        def imap_factory(config):
            return Mock()
        
        # Create two processors with different account IDs
        processor1 = AccountProcessor(
            account_id='account1',
            account_config=sample_account_config,
            imap_client_factory=imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=load_blacklist_rules,
            whitelist_service=load_whitelist_rules,
            note_generator=mock_note_generator,
            parser=parse_html_content,
            decision_logic=mock_decision_logic
        )
        
        processor2 = AccountProcessor(
            account_id='account2',
            account_config=sample_account_config,
            imap_client_factory=imap_factory,
            llm_client=mock_llm_client,
            blacklist_service=load_blacklist_rules,
            whitelist_service=load_whitelist_rules,
            note_generator=mock_note_generator,
            parser=parse_html_content,
            decision_logic=mock_decision_logic
        )
        
        # Verify they have different account IDs
        assert processor1.account_id != processor2.account_id
        
        # Verify they have separate IMAP connections (both None initially)
        assert processor1._imap_conn is None
        assert processor2._imap_conn is None
        
        # Verify they have separate processing contexts
        assert processor1._processing_context is not processor2._processing_context


class TestAccountProcessorSetup:
    """Test AccountProcessor setup() method."""
    
    def test_setup_success(self, account_processor, mock_imap_client):
        """Test successful setup."""
        account_processor.setup()
        
        # Verify IMAP client was created and connected
        assert account_processor._imap_conn is not None
        mock_imap_client.connect.assert_called_once()
        
        # Verify processing context was initialized
        assert account_processor._processing_context['account_id'] == 'test_account'
        assert 'start_time' in account_processor._processing_context
    
    def test_setup_imap_connection_failure(self, account_processor, mock_imap_client):
        """Test setup failure when IMAP connection fails."""
        mock_imap_client.connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(AccountProcessorSetupError):
            account_processor.setup()
        
        # Verify teardown would still work (connection is None)
        assert account_processor._imap_conn is None or not mock_imap_client._connected


class TestAccountProcessorRun:
    """Test AccountProcessor run() method."""
    
    def test_run_without_setup(self, account_processor):
        """Test that run() fails if setup() hasn't been called."""
        with pytest.raises(AccountProcessorRunError):
            account_processor.run()
    
    def test_run_with_no_emails(self, account_processor, mock_imap_client):
        """Test run() when no emails are found."""
        account_processor.setup()
        # Mock count to return zero emails
        mock_imap_client.count_unprocessed_emails.return_value = (0, [])
        # Disable safety interlock for this test
        account_processor.config['safety_interlock'] = {'enabled': False}
        
        account_processor.run()
        
        # Verify no emails were processed
        assert len(account_processor._processed_emails) == 0
        # Verify count_unprocessed_emails was called
        mock_imap_client.count_unprocessed_emails.assert_called_once()
    
    def test_run_processes_emails(self, account_processor, mock_imap_client, 
                                  mock_llm_client, mock_note_generator):
        """Test run() processes emails through the pipeline."""
        account_processor.setup()
        
        # Create sample email data
        email_data = {
            'uid': '123',
            'subject': 'Test Email',
            'from': 'sender@example.com',
            'body': 'Plain text body',
            'html_body': '<p>HTML body</p>'
        }
        # Mock count to return 1 email
        mock_imap_client.count_unprocessed_emails.return_value = (1, ['123'])
        mock_imap_client.get_unprocessed_emails.return_value = [email_data]
        # Disable safety interlock for this test
        account_processor.config['safety_interlock'] = {'enabled': False}
        
        # Mock blacklist to return PASS
        with patch('src.account_processor.check_blacklist', return_value=ActionEnum.PASS):
            account_processor.run()
        
        # Verify email was processed
        assert len(account_processor._processed_emails) == 1
        assert account_processor._processed_emails[0].uid == '123'
        
        # Verify LLM was called
        mock_llm_client.classify_email.assert_called()
        
        # Verify note generator was called
        mock_note_generator.generate_note.assert_called()


class TestAccountProcessorTeardown:
    """Test AccountProcessor teardown() method."""
    
    def test_teardown_cleans_up_resources(self, account_processor, mock_imap_client):
        """Test that teardown() properly cleans up resources."""
        account_processor.setup()
        account_processor.teardown()
        
        # Verify IMAP connection was closed
        mock_imap_client.disconnect.assert_called_once()
        
        # Verify processing context was cleared
        assert account_processor._processing_context == {}
    
    def test_teardown_handles_errors_gracefully(self, account_processor, mock_imap_client):
        """Test that teardown() handles errors without raising."""
        account_processor.setup()
        mock_imap_client.disconnect.side_effect = Exception("Disconnect failed")
        
        # Should not raise
        account_processor.teardown()
        
        # Verify disconnect was attempted
        mock_imap_client.disconnect.assert_called_once()


class TestConfigurableImapClient:
    """Test ConfigurableImapClient class."""
    
    @patch('src.auth.strategies.os.getenv', return_value='test_password')
    def test_create_from_config(self, mock_getenv, sample_account_config):
        """Test creating ConfigurableImapClient from config."""
        client = create_imap_client_from_config(sample_account_config)
        
        assert isinstance(client, ConfigurableImapClient)
        assert not client._connected
    
    def test_create_from_config_missing_fields(self):
        """Test that missing required fields raise error."""
        incomplete_config = {
            'imap': {
                'server': 'imap.test.com'
                # Missing port and username
            }
        }
        
        with pytest.raises(AccountProcessorSetupError):
            create_imap_client_from_config(incomplete_config)
    
    @patch('src.account_processor.imaplib.IMAP4_SSL')
    @patch('src.auth.strategies.os.getenv', return_value='test_password')
    def test_connect_with_config(self, mock_getenv, mock_imap_ssl, sample_account_config):
        """Test connecting with account-specific config."""
        # Mock IMAP connection
        mock_imap = Mock()
        mock_imap.login = Mock()
        mock_imap.select = Mock(return_value=('OK', [b'1']))
        mock_imap_ssl.return_value = mock_imap
        
        client = create_imap_client_from_config(sample_account_config)
        client.connect()
        
        # Verify connection was made with correct server/port
        mock_imap_ssl.assert_called_once_with('imap.test.com', 993)
        # Verify authenticator was used (login called via PasswordAuthenticator)
        mock_imap.login.assert_called_once_with('test@example.com', 'test_password')
        assert client._connected


class TestAccountProcessorPipeline:
    """Test the complete processing pipeline."""
    
    def test_blacklist_drop(self, account_processor, mock_imap_client):
        """Test that blacklist DROP action skips processing."""
        account_processor.setup()
        
        email_data = {
            'uid': '123',
            'subject': 'Spam Email',
            'from': 'spam@example.com',
            'body': 'Spam content'
        }
        # Mock count to return 1 email
        mock_imap_client.count_unprocessed_emails.return_value = (1, ['123'])
        mock_imap_client.get_unprocessed_emails.return_value = [email_data]
        # Disable safety interlock for this test
        account_processor.config['safety_interlock'] = {'enabled': False}
        
        # Mock blacklist to return DROP
        with patch('src.account_processor.check_blacklist', return_value=ActionEnum.DROP):
            account_processor.run()
        
        # Verify email was dropped, not processed
        assert len(account_processor._dropped_emails) == 1
        assert len(account_processor._processed_emails) == 0
    
    def test_blacklist_record(self, account_processor, mock_imap_client, mock_note_generator):
        """Test that blacklist RECORD action generates raw note."""
        account_processor.setup()
        
        email_data = {
            'uid': '123',
            'subject': 'Record Email',
            'from': 'record@example.com',
            'body': 'Record content'
        }
        # Mock count to return 1 email
        mock_imap_client.count_unprocessed_emails.return_value = (1, ['123'])
        mock_imap_client.get_unprocessed_emails.return_value = [email_data]
        # Disable safety interlock for this test
        account_processor.config['safety_interlock'] = {'enabled': False}
        
        # Mock blacklist to return RECORD
        with patch('src.account_processor.check_blacklist', return_value=ActionEnum.RECORD):
            account_processor.run()
        
        # Verify email was recorded, not processed
        assert len(account_processor._recorded_emails) == 1
        assert len(account_processor._processed_emails) == 0
    
    def test_full_pipeline_pass(self, account_processor, mock_imap_client, 
                                mock_llm_client, mock_note_generator, mock_decision_logic):
        """Test full pipeline when email passes blacklist."""
        account_processor.setup()
        
        email_data = {
            'uid': '123',
            'subject': 'Test Email',
            'from': 'sender@example.com',
            'body': 'Plain text',
            'html_body': '<p>HTML content</p>'
        }
        # Mock count to return 1 email
        mock_imap_client.count_unprocessed_emails.return_value = (1, ['123'])
        mock_imap_client.get_unprocessed_emails.return_value = [email_data]
        # Disable safety interlock for this test
        account_processor.config['safety_interlock'] = {'enabled': False}
        
        # Mock blacklist to return PASS
        with patch('src.account_processor.check_blacklist', return_value=ActionEnum.PASS):
            with patch('src.account_processor.apply_whitelist', return_value=(8.0, [])):
                account_processor.run()
        
        # Verify email went through full pipeline
        assert len(account_processor._processed_emails) == 1
        email_context = account_processor._processed_emails[0]
        
        # Verify content was parsed
        assert email_context.parsed_body is not None
        
        # Verify LLM was called
        mock_llm_client.classify_email.assert_called()
        
        # Verify note was generated
        mock_note_generator.generate_note.assert_called()
        
        # Verify email was marked as processed
        mock_imap_client.set_flag.assert_called()


class TestSafetyInterlock:
    """Test safety interlock with cost estimation."""
    
    def test_cost_estimation_token_based(self):
        """Test cost estimation with token-based pricing."""
        model_config = {
            'model': 'test-model',
            'cost_per_1k_tokens': 0.001
        }
        safety_config = {
            'average_tokens_per_email': 2000,
            'currency': '$'
        }
        
        estimate = estimate_processing_cost(
            email_count=10,
            model_config=model_config,
            safety_config=safety_config
        )
        
        assert estimate.email_count == 10
        assert estimate.model_name == 'test-model'
        assert estimate.tokens_per_email == 2000
        assert estimate.estimated_cost == 0.02  # 10 emails * 2000 tokens / 1000 * 0.001
        assert estimate.cost_per_email == 0.002
        assert estimate.currency == '$'
    
    def test_cost_estimation_direct_pricing(self):
        """Test cost estimation with direct per-email pricing."""
        model_config = {
            'model': 'test-model',
            'cost_per_email': 0.005
        }
        safety_config = {
            'currency': '$'
        }
        
        estimate = estimate_processing_cost(
            email_count=5,
            model_config=model_config,
            safety_config=safety_config
        )
        
        assert estimate.email_count == 5
        assert estimate.estimated_cost == 0.025  # 5 emails * 0.005
        assert estimate.cost_per_email == 0.005
        assert estimate.tokens_per_email == 0  # Not applicable for direct pricing
    
    def test_cost_estimation_zero_emails(self):
        """Test cost estimation with zero emails."""
        model_config = {
            'model': 'test-model',
            'cost_per_1k_tokens': 0.001
        }
        
        estimate = estimate_processing_cost(
            email_count=0,
            model_config=model_config
        )
        
        assert estimate.email_count == 0
        assert estimate.estimated_cost == 0.0
        assert estimate.cost_per_email == 0.0
    
    def test_cost_estimation_missing_config(self):
        """Test cost estimation raises error with missing config."""
        model_config = {
            'model': 'test-model'
            # Missing cost_per_1k_tokens and cost_per_email
        }
        
        with pytest.raises(ValueError, match="cost_per_email.*cost_per_1k_tokens"):
            estimate_processing_cost(
                email_count=10,
                model_config=model_config
            )
    
    def test_cost_estimation_negative_count(self):
        """Test cost estimation raises error with negative email count."""
        model_config = {
            'model': 'test-model',
            'cost_per_1k_tokens': 0.001
        }
        
        with pytest.raises(ValueError, match="non-negative"):
            estimate_processing_cost(
                email_count=-1,
                model_config=model_config
            )
    
    @patch('builtins.input', return_value='yes')
    def test_prompt_user_confirmation_yes(self, mock_input):
        """Test user confirmation with 'yes' response."""
        estimate = CostEstimate(
            email_count=10,
            estimated_cost=0.05,
            currency='$',
            cost_per_email=0.005,
            tokens_per_email=2000,
            model_name='test-model',
            breakdown={}
        )
        
        result = prompt_user_confirmation(estimate)
        
        assert result is True
        mock_input.assert_called_once()
    
    @patch('builtins.input', return_value='no')
    def test_prompt_user_confirmation_no(self, mock_input):
        """Test user confirmation with 'no' response."""
        estimate = CostEstimate(
            email_count=10,
            estimated_cost=0.05,
            currency='$',
            cost_per_email=0.005,
            tokens_per_email=2000,
            model_name='test-model',
            breakdown={}
        )
        
        result = prompt_user_confirmation(estimate)
        
        assert result is False
        mock_input.assert_called_once()
    
    def test_prompt_user_confirmation_custom_callback(self):
        """Test user confirmation with custom callback."""
        estimate = CostEstimate(
            email_count=10,
            estimated_cost=0.05,
            currency='$',
            cost_per_email=0.005,
            tokens_per_email=2000,
            model_name='test-model',
            breakdown={}
        )
        
        def mock_callback(prompt):
            return 'yes'
        
        result = prompt_user_confirmation(estimate, confirmation_callback=mock_callback)
        
        assert result is True
    
    def test_safety_interlock_count_emails(self, account_processor, mock_imap_client):
        """Test that safety interlock counts emails before fetching."""
        account_processor.setup()
        
        # Mock count_unprocessed_emails to return email count and UIDs
        mock_imap_client.count_unprocessed_emails = Mock(return_value=(5, ['1', '2', '3', '4', '5']))
        mock_imap_client.get_unprocessed_emails = Mock(return_value=[])
        
        # Configure safety interlock
        account_processor.config['safety_interlock'] = {
            'enabled': True,
            'cost_threshold': 0.10,
            'skip_confirmation_below_threshold': False
        }
        account_processor.config['classification'] = {
            'model': 'test-model',
            'cost_per_1k_tokens': 0.001
        }
        
        # Mock confirmation to return True
        def mock_confirmation(prompt):
            return 'yes'
        account_processor._confirmation_callback = mock_confirmation
        
        account_processor.run()
        
        # Verify count_unprocessed_emails was called
        mock_imap_client.count_unprocessed_emails.assert_called_once()
    
    def test_safety_interlock_zero_emails(self, account_processor, mock_imap_client):
        """Test safety interlock with zero emails (should exit early)."""
        account_processor.setup()
        
        # Mock count_unprocessed_emails to return zero emails
        mock_imap_client.count_unprocessed_emails = Mock(return_value=(0, []))
        
        account_processor.run()
        
        # Verify get_unprocessed_emails was NOT called (early exit)
        mock_imap_client.get_unprocessed_emails.assert_not_called()
    
    def test_safety_interlock_below_threshold(self, account_processor, mock_imap_client):
        """Test safety interlock skips confirmation when cost is below threshold."""
        account_processor.setup()
        
        # Mock count_unprocessed_emails to return 1 email
        mock_imap_client.count_unprocessed_emails = Mock(return_value=(1, ['1']))
        mock_imap_client.get_unprocessed_emails = Mock(return_value=[])
        
        # Configure safety interlock with threshold
        account_processor.config['safety_interlock'] = {
            'enabled': True,
            'cost_threshold': 0.10,
            'skip_confirmation_below_threshold': True,
            'average_tokens_per_email': 2000
        }
        account_processor.config['classification'] = {
            'model': 'test-model',
            'cost_per_1k_tokens': 0.001  # 1 email * 2000 tokens / 1000 * 0.001 = 0.002 (below threshold)
        }
        
        account_processor.run()
        
        # Verify get_unprocessed_emails was called (no confirmation needed)
        mock_imap_client.get_unprocessed_emails.assert_called_once()
    
    def test_safety_interlock_user_cancels(self, account_processor, mock_imap_client):
        """Test safety interlock when user cancels confirmation."""
        account_processor.setup()
        
        # Mock count_unprocessed_emails to return emails
        mock_imap_client.count_unprocessed_emails = Mock(return_value=(10, ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']))
        
        # Configure safety interlock
        account_processor.config['safety_interlock'] = {
            'enabled': True,
            'cost_threshold': 0.10,
            'skip_confirmation_below_threshold': False
        }
        account_processor.config['classification'] = {
            'model': 'test-model',
            'cost_per_1k_tokens': 0.001
        }
        
        # Mock confirmation to return False (user cancels)
        def mock_confirmation(prompt):
            return 'no'
        account_processor._confirmation_callback = mock_confirmation
        
        account_processor.run()
        
        # Verify get_unprocessed_emails was NOT called (user cancelled)
        mock_imap_client.get_unprocessed_emails.assert_not_called()
    
    def test_safety_interlock_disabled(self, account_processor, mock_imap_client):
        """Test that safety interlock can be disabled."""
        account_processor.setup()
        
        # Mock count_unprocessed_emails
        mock_imap_client.count_unprocessed_emails = Mock(return_value=(5, ['1', '2', '3', '4', '5']))
        mock_imap_client.get_unprocessed_emails = Mock(return_value=[])
        
        # Configure safety interlock as disabled
        account_processor.config['safety_interlock'] = {
            'enabled': False
        }
        
        account_processor.run()
        
        # Verify get_unprocessed_emails was called (interlock disabled)
        mock_imap_client.get_unprocessed_emails.assert_called_once()
    
    def test_safety_interlock_cost_estimation_failure(self, account_processor, mock_imap_client):
        """Test safety interlock handles cost estimation failures gracefully."""
        account_processor.setup()
        
        # Mock count_unprocessed_emails
        mock_imap_client.count_unprocessed_emails = Mock(return_value=(5, ['1', '2', '3', '4', '5']))
        mock_imap_client.get_unprocessed_emails = Mock(return_value=[])
        
        # Configure safety interlock but with missing cost config (will fail estimation)
        account_processor.config['safety_interlock'] = {
            'enabled': True
        }
        account_processor.config['classification'] = {
            'model': 'test-model'
            # Missing cost_per_1k_tokens and cost_per_email
        }
        
        # Should continue without cost check (logs warning)
        account_processor.run()
        
        # Verify get_unprocessed_emails was called (continues despite estimation failure)
        mock_imap_client.get_unprocessed_emails.assert_called_once()
