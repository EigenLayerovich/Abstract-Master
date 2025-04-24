import datetime

from data.auto_repr import AutoRepr
from sqlalchemy import Column, Integer, Text, Boolean, DateTime
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Accounts(Base, AutoRepr):
    __tablename__ = 'accounts'

    id = Column(Integer, primary_key=True)

    evm_pk = Column(Text, unique=True)
    evm_address = Column(Text, unique=True)
    proxy = Column(Text)
    email = Column(Text)

    # twitter
    twitter_token = Column(Text)
    twitter_account_status = Column(Text)

    # discord
    discord_token = Column(Text)
    user_agent = Column(Text)

    # galxe 
    abstract_register = Column(Boolean)
    privy_pk = Column(Text)
    privy_address = Column(Text)
    abstract_smartwallet = Column(Text)
    abstract_twitter_connected = Column(Boolean)
    bridge_complete = Column(Boolean)
    abstract_discord_connected = Column(Boolean)
    abstract_pw_cookies = Column(Text)
    abstract_pw_storage = Column(Text)
    abstract_pw_cookies_expired = Column(DateTime)

    # badges
    badge_twitter = Column(Boolean)
    badge_discord = Column(Boolean)
    badge_fund_your_account = Column(Boolean)
    badge_app_voter = Column(Boolean)
    badge_the_trader = Column(Boolean)


    # stats
    claimed_badges = Column(Integer)
    badges_parse_finished = Column(Boolean)

    # vote
    abstract_vote = Column(Boolean)

    # swap
    abstract_swap = Column(DateTime)

    finished = Column(Boolean)
    

    def __init__(
            self,
            evm_pk: str,
            evm_address: str,
            proxy: str,
            email: str,
            twitter_token: str,
            discord_token: str,
            user_agent: str,
    ) -> None:
        
        self.evm_pk = evm_pk
        self.evm_address = evm_address
        self.proxy = proxy
        self.email = email

        # twitter
        self.twitter_token = twitter_token
        self.twitter_account_status = 'OK'

        # discord
        self.discord_token = discord_token
        self.user_agent = user_agent

        # abstract
        self.abstract_register = False
        self.abstract_pw_cookies = ''
        self.abstract_pw_storage = ''
        self.abstract_pw_cookies_expired = datetime.datetime(1970, 1, 1)

        self.privy_pk = ''
        self.privy_address = ''
        self.abstract_smartwallet = ''
        self.abstract_twitter_connected = False
        self.bridge_complete = False
        self.abstract_discord_connected = False
        
        # badges
        self.badge_twitter = False
        self.badge_discord = False
        self.badge_fund_your_account = False
        self.badge_the_trader = False
        self.badge_app_voter = False

        # stats
        self.claimed_badges = 0
        self.badges_parse_finished = False

        # vote
        self.abstract_vote = False

        # swap
        self.abstract_swap = datetime.datetime(1970, 1, 1)

        self.finished = False