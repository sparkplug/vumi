"""Tests for vumi.demos.ircbot."""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.application.tests.utils import ApplicationTestCase

from vumi.demos.ircbot import MemoWorker
from vumi.message import TransportUserMessage


class TestMemoWorker(ApplicationTestCase):

    application_class = MemoWorker

    @inlineCallbacks
    def setUp(self):
        super(TestMemoWorker, self).setUp()
        self.worker = yield self.get_application({'worker_name': 'testmemo'})
        yield self.worker.redis._purge_all()  # just in case

    @inlineCallbacks
    def send(self, content, from_addr='testnick', channel=None):
        transport_metadata = {}
        helper_metadata = {}
        if channel is not None:
            transport_metadata['irc_channel'] = channel
            helper_metadata['irc'] = {'irc_channel': channel}

        msg = self.mkmsg_in(content=content, from_addr=from_addr,
                            helper_metadata=helper_metadata,
                            transport_metadata=transport_metadata)
        yield self.dispatch(msg)

    @inlineCallbacks
    def recv(self, n=0):
        msgs = yield self.wait_for_dispatched_messages(n)

        def reply_code(msg):
            if msg['session_event'] == TransportUserMessage.SESSION_CLOSE:
                return 'end'
            return 'reply'

        returnValue([(reply_code(msg), msg['content']) for msg in msgs])

    @inlineCallbacks
    def test_no_memos(self):
        yield self.send("Message from someone with no messages.")
        replies = yield self.recv()
        self.assertEquals([], replies)

    @inlineCallbacks
    def test_leave_memo(self):
        yield self.send('bot: tell memoed hey there', channel='#test')
        memos = yield self.worker.retrieve_memos('#test', 'memoed')
        self.assertEquals(memos, [['testnick', 'hey there']])
        replies = yield self.recv()
        self.assertEqual(replies, [
            ('reply', 'testnick: Sure thing, boss.'),
            ])

    @inlineCallbacks
    def test_leave_memo_nick_canonicalization(self):
        yield self.send('bot: tell MeMoEd hey there', channel='#test')
        memos = yield self.worker.retrieve_memos('#test', 'memoed')
        self.assertEquals(memos, [['testnick', 'hey there']])

    @inlineCallbacks
    def test_send_memos(self):
        yield self.send('bot: tell testmemo this is memo 1', channel='#test')
        yield self.send('bot: tell testmemo this is memo 2', channel='#test')
        yield self.send('bot: tell testmemo this is a different channel',
                        channel='#another')

        # replies to setting memos
        replies = yield self.recv(3)
        self.clear_dispatched_outbound()

        yield self.send('ping', channel='#test', from_addr='testmemo')
        replies = yield self.recv(2)
        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is memo 1'),
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is memo 2'),
            ])
        self.clear_dispatched_outbound()

        yield self.send('ping', channel='#another', from_addr='testmemo')
        replies = yield self.recv(1)
        self.assertEqual(replies, [
            ('reply', 'testmemo, testnick asked me tell you:'
             ' this is a different channel'),
            ])
