"""Business operations for Discord verification configuration.

Storage is normalized across ``guild_settings`` (scalars) plus
``guild_role_bindings`` / ``guild_channel_bindings`` (IDs). The service presents
a flat ``ConfigurationView`` so the API contract and OAuth flow are unchanged.
"""

from uuid import UUID

from app.models.enums import GuildChannelPurpose, GuildRolePurpose, RiskAction
from app.models.guild_bindings import GuildChannelBinding, GuildRoleBinding
from app.models.guild_settings import GuildSettings
from app.repositories.configuration_repository import (
    ConfigurationRepository,
)
from app.services.views import ConfigurationView


def normalize_verification_state(
    enabled: bool,
    deny_vpn_or_proxy: bool,
    deny_shared_ip: bool,
) -> tuple[bool, bool, bool]:
    """Return a valid (master, vpn, shared) verification state.

    The only invalid combination is master ON with both detectors OFF; it is
    normalized to fully OFF so the master never implies "verification on" with
    nothing actually screening members.
    """

    if enabled and not deny_vpn_or_proxy and not deny_shared_ip:
        return (False, False, False)
    return (enabled, deny_vpn_or_proxy, deny_shared_ip)


def resolve_verification_state(
    current: tuple[bool, bool, bool],
    *,
    enabled: bool | None = None,
    deny_vpn_or_proxy: bool | None = None,
    deny_shared_ip: bool | None = None,
) -> tuple[bool, bool, bool]:
    """Apply one verification state-machine intent to a current state.

    ``current`` is ``(master, vpn, shared)``. Exactly one intent is expected:
    - master ON  -> both detectors ON;
    - master OFF -> both detectors OFF;
    - a detector intent sets that detector, then the master is derived (any
      detector ON -> master ON; both OFF -> master OFF).
    The result is always a valid (normalized) state.
    """

    cur_enabled, cur_vpn, cur_shared = current

    if enabled is not None:
        cur_enabled = cur_vpn = cur_shared = bool(enabled)
    else:
        if deny_vpn_or_proxy is not None:
            cur_vpn = bool(deny_vpn_or_proxy)
        if deny_shared_ip is not None:
            cur_shared = bool(deny_shared_ip)
        cur_enabled = cur_vpn or cur_shared

    return normalize_verification_state(cur_enabled, cur_vpn, cur_shared)


class ConfigurationService:
    """Manage verification settings for Discord guilds."""

    def __init__(
        self,
        configuration_repository: ConfigurationRepository,
    ) -> None:
        """Initialize the service with its configuration repository."""

        self._configuration_repository = configuration_repository

    async def _assemble(
        self,
        settings: GuildSettings,
    ) -> ConfigurationView:
        """Build a flat view from stored settings and bindings."""

        role_map = await self._configuration_repository.get_role_bindings(
            settings.guild_id
        )
        channel_map = await self._configuration_repository.get_channel_bindings(
            settings.guild_id
        )

        def role(purpose: GuildRolePurpose) -> str:
            binding = role_map.get(purpose)
            return binding.role_id if binding is not None else ""

        def channel(purpose: GuildChannelPurpose) -> str:
            binding = channel_map.get(purpose)
            return binding.channel_id if binding is not None else ""

        # Present a valid state even if a legacy/invalid row slipped through.
        enabled, deny_vpn_or_proxy, deny_shared_ip = normalize_verification_state(
            settings.enabled,
            settings.deny_vpn_or_proxy,
            settings.deny_shared_ip,
        )

        return ConfigurationView(
            id=settings.id,
            guild_id=settings.guild_id,
            verification_channel_id=channel(GuildChannelPurpose.VERIFICATION),
            log_channel_id=channel(GuildChannelPurpose.LOG),
            unverified_role_id=role(GuildRolePurpose.UNVERIFIED),
            member_role_id=role(GuildRolePurpose.MEMBER),
            manual_review_role_id=role(GuildRolePurpose.MANUAL_REVIEW),
            minimum_account_age_days=settings.minimum_account_age_days,
            session_timeout_seconds=settings.session_timeout_seconds,
            deny_vpn_or_proxy=deny_vpn_or_proxy,
            deny_shared_ip=deny_shared_ip,
            vpn_or_proxy_action=settings.vpn_or_proxy_action,
            shared_ip_action=settings.shared_ip_action,
            enabled=enabled,
            panel_message_id=settings.panel_message_id,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    async def get_by_guild_id(
        self,
        guild_id: UUID,
    ) -> ConfigurationView | None:
        """Return the configuration belonging to a Discord guild."""

        settings = await self._configuration_repository.get_settings(guild_id)

        if settings is None:
            return None

        return await self._assemble(settings)

    async def create_or_update(
        self,
        *,
        guild_id: UUID,
        verification_channel_id: str,
        log_channel_id: str,
        unverified_role_id: str,
        member_role_id: str,
        manual_review_role_id: str,
        minimum_account_age_days: int,
        session_timeout_seconds: int,
        deny_vpn_or_proxy: bool,
        deny_shared_ip: bool,
        enabled: bool,
        vpn_or_proxy_action: RiskAction = RiskAction.DENY,
        shared_ip_action: RiskAction = RiskAction.DENY,
    ) -> ConfigurationView:
        """Create or update the verification configuration for a guild."""

        enabled, deny_vpn_or_proxy, deny_shared_ip = normalize_verification_state(
            enabled, deny_vpn_or_proxy, deny_shared_ip
        )

        settings = await self._configuration_repository.get_settings(guild_id)

        if settings is None:
            settings = GuildSettings(
                guild_id=guild_id,
                minimum_account_age_days=minimum_account_age_days,
                session_timeout_seconds=session_timeout_seconds,
                deny_vpn_or_proxy=deny_vpn_or_proxy,
                deny_shared_ip=deny_shared_ip,
                vpn_or_proxy_action=vpn_or_proxy_action,
                shared_ip_action=shared_ip_action,
                enabled=enabled,
            )
            await self._configuration_repository.add(settings)
        else:
            settings.minimum_account_age_days = minimum_account_age_days
            settings.session_timeout_seconds = session_timeout_seconds
            settings.deny_vpn_or_proxy = deny_vpn_or_proxy
            settings.deny_shared_ip = deny_shared_ip
            settings.vpn_or_proxy_action = vpn_or_proxy_action
            settings.shared_ip_action = shared_ip_action
            settings.enabled = enabled

        await self._sync_role_binding(
            guild_id, GuildRolePurpose.UNVERIFIED, unverified_role_id
        )
        await self._sync_role_binding(guild_id, GuildRolePurpose.MEMBER, member_role_id)
        await self._sync_optional_role_binding(
            guild_id, GuildRolePurpose.MANUAL_REVIEW, manual_review_role_id
        )
        await self._sync_channel_binding(
            guild_id, GuildChannelPurpose.VERIFICATION, verification_channel_id
        )
        # Preserve legacy log binding when the client omits/clears the field so
        # Discord Logs dual-read and rolling deploys do not lose the channel.
        if str(log_channel_id or "").strip():
            await self._sync_channel_binding(
                guild_id, GuildChannelPurpose.LOG, log_channel_id
            )

        await self._configuration_repository.flush()
        await self._configuration_repository.refresh(settings)

        return await self._assemble(settings)

    async def _sync_role_binding(
        self,
        guild_id: UUID,
        purpose: GuildRolePurpose,
        role_id: str,
    ) -> None:
        role_map = await self._configuration_repository.get_role_bindings(guild_id)
        binding = role_map.get(purpose)
        if binding is None:
            await self._configuration_repository.add(
                GuildRoleBinding(guild_id=guild_id, purpose=purpose, role_id=role_id)
            )
        else:
            binding.role_id = role_id

    async def _sync_optional_role_binding(
        self,
        guild_id: UUID,
        purpose: GuildRolePurpose,
        role_id: str,
    ) -> None:
        """Sync an optional role binding, removing it when cleared."""

        role_map = await self._configuration_repository.get_role_bindings(guild_id)
        binding = role_map.get(purpose)

        if not role_id:
            if binding is not None:
                await self._configuration_repository.delete(binding)
            return

        if binding is None:
            await self._configuration_repository.add(
                GuildRoleBinding(guild_id=guild_id, purpose=purpose, role_id=role_id)
            )
        else:
            binding.role_id = role_id

    async def _sync_channel_binding(
        self,
        guild_id: UUID,
        purpose: GuildChannelPurpose,
        channel_id: str,
    ) -> None:
        channel_map = await self._configuration_repository.get_channel_bindings(guild_id)
        binding = channel_map.get(purpose)
        if binding is None:
            await self._configuration_repository.add(
                GuildChannelBinding(
                    guild_id=guild_id, purpose=purpose, channel_id=channel_id
                )
            )
        else:
            binding.channel_id = channel_id

    async def apply_verification_state(
        self,
        *,
        guild_id: UUID,
        enabled: bool | None = None,
        deny_vpn_or_proxy: bool | None = None,
        deny_shared_ip: bool | None = None,
    ) -> ConfigurationView:
        """Apply the Member Verification master/detector state machine atomically.

        This is the single authoritative transition for the (master, vpn,
        shared) tri-state. A bare ``GuildSettings`` row is created on demand so
        the toggles work before channels/roles are configured.

        Rules:
        - ``enabled=True``  -> master ON, both detectors ON.
        - ``enabled=False`` -> master OFF, both detectors OFF.
        - a detector intent sets that detector, then the master is derived:
          any detector ON -> master ON; both OFF -> master OFF (auto-disable).
        The invalid master-ON/both-OFF combination can never be persisted.
        """

        settings = await self._configuration_repository.get_settings(guild_id)

        if settings is None:
            # Start a fresh row fully OFF; the requested intent is applied
            # below. Explicit values keep the pre-flush reads well-defined.
            settings = GuildSettings(
                guild_id=guild_id,
                enabled=False,
                deny_vpn_or_proxy=False,
                deny_shared_ip=False,
            )
            await self._configuration_repository.add(settings)

        next_enabled, next_vpn, next_shared = resolve_verification_state(
            (
                settings.enabled,
                settings.deny_vpn_or_proxy,
                settings.deny_shared_ip,
            ),
            enabled=enabled,
            deny_vpn_or_proxy=deny_vpn_or_proxy,
            deny_shared_ip=deny_shared_ip,
        )

        settings.enabled = next_enabled
        settings.deny_vpn_or_proxy = next_vpn
        settings.deny_shared_ip = next_shared

        await self._configuration_repository.flush()
        # Server-default timestamps (created_at/updated_at) are NULL in-Python
        # until refresh; ConfigurationResponse requires non-null datetimes.
        await self._configuration_repository.refresh(settings)

        return await self._assemble(settings)

    async def patch_detectors(
        self,
        *,
        guild_id: UUID,
        deny_vpn_or_proxy: bool | None = None,
        vpn_or_proxy_action: RiskAction | None = None,
        deny_shared_ip: bool | None = None,
        shared_ip_action: RiskAction | None = None,
    ) -> ConfigurationView | None:
        """Partially update the risk-detector settings for a guild.

        Only the provided fields are changed, so the detector mini-cards can
        persist a single toggle or action without resubmitting the full
        (channel/role) configuration payload.
        """

        settings = await self._configuration_repository.get_settings(guild_id)

        if settings is None:
            return None

        if deny_vpn_or_proxy is not None:
            settings.deny_vpn_or_proxy = deny_vpn_or_proxy
        if vpn_or_proxy_action is not None:
            settings.vpn_or_proxy_action = vpn_or_proxy_action
        if deny_shared_ip is not None:
            settings.deny_shared_ip = deny_shared_ip
        if shared_ip_action is not None:
            settings.shared_ip_action = shared_ip_action

        await self._configuration_repository.flush()
        # onupdate=func.now() expires updated_at; refresh before assemble so
        # ConfigurationResponse does not see NULL / MissingGreenlet (HTTP 500).
        await self._configuration_repository.refresh(settings)

        return await self._assemble(settings)

    async def set_enabled(
        self,
        *,
        guild_id: UUID,
        enabled: bool,
    ) -> ConfigurationView | None:
        """Enable or disable verification for an existing configuration."""

        settings = await self._configuration_repository.get_settings(guild_id)

        if settings is None:
            return None

        settings.enabled = enabled
        await self._configuration_repository.flush()
        await self._configuration_repository.refresh(settings)

        return await self._assemble(settings)
