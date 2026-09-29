# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Windows desktop session base class.
This module provides HostAgent initialization for UFO² sessions.
"""


from ufo.agents.agent.host_agent import AgentFactory, HostAgent
from config.config_loader import get_ufo_config
from ufo.module.basic import BaseSession

ufo_config = get_ufo_config()


class WindowsBaseSession(BaseSession):
    """
    Base class for all Windows-based sessions.
    Provides Windows-specific functionality like HostAgent initialization.
    Windows sessions use a two-tier architecture: HostAgent -> AppAgent.
    """

    def _init_agents(self) -> None:
        """
        Initialize Windows-specific agents, including the HostAgent.
        The HostAgent is responsible for task planning and coordination in Windows sessions.
        """
        self._host_agent: HostAgent = AgentFactory.create_agent(
            "host",
            "HostAgent",
            ufo_config.host_agent.visual_mode,
            ufo_config.system.HOSTAGENT_PROMPT,
            ufo_config.system.HOSTAGENT_EXAMPLE_PROMPT,
            ufo_config.system.API_PROMPT,
        )

    def reset(self):
        """
        Reset the session state for a new session.
        This includes resetting the host agent and any other session-specific state.
        """
        self._host_agent.set_state(self._host_agent.default_state)
