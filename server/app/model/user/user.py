# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Hanggent.AI All Rights Reserved. =========

from datetime import date, datetime
from enum import IntEnum
import logging
from typing import Any

from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import Float, Integer, JSON, SmallInteger, String, text
from sqlalchemy_utils import ChoiceType
from sqlmodel import Column, Field, Session, col, select

from app.component.encrypt import password_hash
from app.model.abstract.model import AbstractModel, DefaultTimes

logger = logging.getLogger("user_model")


class Status(IntEnum):
    Normal = 1
    Block = -1


class User(AbstractModel, DefaultTimes, table=True):
    id: int = Field(default=None, primary_key=True)
    stack_id: str | None = Field(default=None, unique=True, max_length=255)
    username: str | None = Field(default=None, unique=True, max_length=128)
    email: EmailStr = Field(unique=True, max_length=128)
    password: str | None = Field(default=None, max_length=256)
    avatar: str = Field(default="", max_length=256)
    nickname: str = Field(default="", max_length=64)
    fullname: str = Field(default="", max_length=128)
    work_desc: str = Field(default="", max_length=255)
    credits: float = Field(default=0.0, description="credits", sa_column=Column(Float, server_default=text("0")))
    last_daily_credit_date: date | None = Field(default=None, description="Last date daily credits were granted")
    last_monthly_credit_date: date | None = Field(default=None, description="Last month monthly credits were granted")
    inviter_user_id: int | None = Field(default=None, foreign_key="user.id", description="Inviter user ID")
    invite_code: str | None = Field(
        default=None, sa_column=Column(String(32), unique=True, nullable=True),
        description="Unique referral/invite code for this user",
    )
    status: Status = Field(default=Status.Normal.value, sa_column=Column(ChoiceType(Status, SmallInteger())))
    # Stripe / subscription fields (added by migration add_stripe_fields_to_user)
    stripe_customer_id: str | None = Field(
        default=None, sa_column=Column(String(255), unique=True, nullable=True)
    )
    subscription_plan: str = Field(
        default="free", sa_column=Column(String(32), server_default=text("'free'"), nullable=False)
    )
    stripe_subscription_id: str | None = Field(
        default=None, sa_column=Column(String(255), nullable=True)
    )
    subscription_status: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    subscription_period_end: datetime | None = Field(
        default=None, description="Subscription period end date"
    )
    # Token billing fields (added by migration add_token_billing_fields)
    spending_limit: float | None = Field(
        default=None, description="User's monthly spending limit for pay-per-use"
    )
    monthly_spending_alert_sent: bool = Field(
        default=False, description="Whether spending alert has been sent this month"
    )
    # OpenClaw bot channel configuration (JSON)
    # Structure: {"telegram": {"mode": "shared"|"own", "botToken": "...", "chatId": ...}, ...}
    bot_channels: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Per-user messaging channel configuration for OpenClaw bot",
    )

    def refresh_credits_on_active(self, session: Session) -> None:
        """Refresh daily credits when user is active.

        Grants daily credits if they haven't been granted today,
        based on the user's subscription plan.
        """
        from app.model.user.user_credits_record import (
            CreditsChannel,
            UserCreditsRecord,
        )

        today = date.today()
        changed = False

        # --- Daily credits ---
        if self.last_daily_credit_date != today:
            try:
                from app.component.stripe_config import SubscriptionPlan, get_plan_config

                plan = SubscriptionPlan(self.subscription_plan or "free")
                plan_config = get_plan_config(plan)
                # Spread monthly free tokens across ~30 days
                daily_amount = plan_config.free_tokens // 30
            except Exception:
                daily_amount = 2700  # fallback: ~80K / 30

            if daily_amount > 0:
                # Mark any previous unused daily records as used
                old_daily = session.exec(
                    select(UserCreditsRecord)
                    .where(UserCreditsRecord.user_id == self.id)
                    .where(UserCreditsRecord.channel == CreditsChannel.daily)
                    .where(UserCreditsRecord.used == False)
                ).all()
                for rec in old_daily:
                    rec.used = True
                    rec.used_at = datetime.now()
                    session.add(rec)

                # Create today's daily credits record
                daily_record = UserCreditsRecord(
                    user_id=self.id,
                    amount=daily_amount,
                    balance=0,
                    channel=CreditsChannel.daily,
                    remark=f"Daily credits for {today}",
                    expire_at=datetime.combine(today, datetime.max.time()),
                )
                session.add(daily_record)

            self.last_daily_credit_date = today
            changed = True
            logger.debug(
                "Granted daily credits",
                extra={"user_id": self.id, "amount": daily_amount},
            )

        if changed:
            session.add(self)
            session.commit()
            session.refresh(self)


class UserProfile(BaseModel):
    fullname: str = ""
    nickname: str = ""
    work_desc: str = ""


class LoginByPasswordIn(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    email: EmailStr
    username: str | None = None
    user_id: int | None = None


class UserIn(BaseModel):
    username: str


class UserCreate(UserIn):
    password: str


class UserOut(BaseModel):
    email: EmailStr
    avatar: str | None = ""
    username: str | None = ""
    nickname: str | None = ""
    fullname: str | None = ""
    work_desc: str | None = ""
    credits: float
    status: Status
    created_at: datetime


class UpdatePassword(BaseModel):
    password: str
    new_password: str
    re_new_password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    invite_code: str | None = None

    @field_validator("password", mode="before")
    def password_strength(cls, v):
        # At least 8 chars, must contain letters and numbers
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain both letters and numbers")
        return v

    @field_validator("password", mode="after")
    def password_hash(cls, v):
        return password_hash(v)
