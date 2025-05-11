from typing import Optional

from ares import AresBot
from collections import defaultdict
from os import getcwd, path
from typing import DefaultDict, Dict, List, Optional, Set, Tuple, Union

import yaml
from cython_extensions import cy_unit_pending
from loguru import logger
from s2clientprotocol.raw_pb2 import Unit as RawUnit
from sc2.constants import ALL_GAS, IS_PLACEHOLDER, FakeEffectID, geyser_ids, mineral_ids
from sc2.data import Race, Result, race_gas, race_townhalls, race_worker
from sc2.dicts.unit_train_build_abilities import TRAIN_INFO
from sc2.game_data import Cost
from sc2.game_state import EffectData
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from ares.behavior_exectioner import BehaviorExecutioner # type: ignore
from ares.behaviors.behavior import Behavior
from ares.build_runner.build_order_runner import BuildOrderRunner
from ares.config_parser import ConfigParser
from ares.consts import (
    ADD_ONS,
    ADD_SHADES_ON_FRAME,
    ALL_STRUCTURES,
    CHAT_DEBUG,
    CONFIG_FILE,
    DEBUG,
    DEBUG_GAME_STEP,
    DEBUG_OPTIONS,
    GAME_STEP,
    GATEWAY_UNITS,
    ID,
    IGNORE_DESTRUCTABLES,
    RACE_SUPPLY,
    SHADE_COMMENCED,
    SHADE_DURATION,
    SHADE_OWNER,
    TECHLAB_TYPES,
    UNITS_TO_AVOID_TYPES,
    USE_DATA,
    WORKER_TYPES,
    UnitRole,
    UnitTreeQueryType,
)
from ares.behaviors.macro import (
    AutoSupply,
    BuildWorkers,
    ExpansionController,
    GasBuildingController,
    MacroPlan,
    Mining,
    ProductionController,
    SpawnController,
)
from ares.custom_bot_ai import CustomBotAI
from ares.dicts.cost_dict import COST_DICT
from ares.dicts.enemy_detector_ranges import DETECTOR_RANGES
from ares.dicts.enemy_vs_ground_static_defense_ranges import (
    ENEMY_VS_GROUND_STATIC_DEFENSE_TYPES,
)
from ares.managers.hub import Hub
from ares.managers.manager_mediator import ManagerMediator

class Voltron(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
        """Initiate custom bot

        Parameters
        ----------
        game_step_override :
            If provided, set the game_step to this value regardless of how it was
            specified elsewhere
        """
        super().__init__(game_step_override)


    async def on_start(self) -> None:
        # await super(Voltron, self).on_start()

        # manually skip the frames in realtime
        if self.realtime:
            self.client.game_step = 1
        elif self.game_step_override:
            self.client.game_step = self.game_step_override
        else:
            # set the game step from config
            self.client.game_step = (
                self.config[GAME_STEP]
                if not self.config[DEBUG]
                else self.config[DEBUG_GAME_STEP]
            )

        if not self.enemy_start_locations or not self.townhalls:
            self.arcade_mode = True

        self.register_managers()

        self.build_order_runner: BuildOrderRunner = BuildOrderRunner(
            self,
            self.manager_hub.data_manager.chosen_opening,
            self.config,
            self.manager_hub.manager_mediator,
        )
        self.behavior_executioner: BehaviorExecutioner = BehaviorExecutioner(
            self, self.config, self.manager_hub.manager_mediator
        )

        if self.config[DEBUG] and self.config[DEBUG_OPTIONS][CHAT_DEBUG]:
            from ares.chat_debug import ChatDebug

            self.chat_debug = ChatDebug(self)

        self.cost_dict: Dict[UnitID, Cost] = COST_DICT
    
        

    async def on_step(self, iteration: int) -> None:
        # await super(Voltron, self).on_step(iteration)

        if self.realtime and self.last_game_loop + 4 > self.state.game_loop:
            return

        self.last_game_loop = self.state.game_loop

        await self.manager_hub.update_managers(self.actual_iteration)
        if not self.build_order_runner.build_completed:
            await self.build_order_runner.run_build()

        self.actual_iteration += 1
        if self.chat_debug:
            # trunk-ignore(mypy/unreachable)
            await self.chat_debug.parse_commands()

        self.register_behavior(Mining())

        
    async def _after_step(self) -> int:
        self.behavior_executioner.execute()
        for drop_action in self._drop_unload_actions:
            await self.unload_container(drop_action[0], drop_action[1])
        for same_order in self._same_order_actions:
            await self._give_units_same_order(
                same_order[0], same_order[1], same_order[2]
            )
        for archon_morph_action in self._archon_morph_actions:
            await self._do_archon_morph(archon_morph_action)
        self.manager_hub.grid_manager.reset_grids(self.actual_iteration)
        await self.manager_hub.warp_in_manager.do_warp_ins()
        return await super(AresBot, self)._after_step()

    """
    Can use `python-sc2` hooks as usual, but make a call the inherited method in the superclass
    Examples:
    """
    #
    # async def on_end(self, game_result: Result) -> None:
    #     await super(Voltron, self).on_end(game_result)
    #
    #     # custom on_end logic here ...
    #
    # async def on_building_construction_complete(self, unit: Unit) -> None:
    #     await super(Voltron, self).on_building_construction_complete(unit)
    #
    #     # custom on_building_construction_complete logic here ...
    #
    # async def on_unit_created(self, unit: Unit) -> None:
    #     await super(Voltron, self).on_unit_created(unit)
    #
    #     # custom on_unit_created logic here ...
    #
    # async def on_unit_destroyed(self, unit_tag: int) -> None:
    #     await super(Voltron, self).on_unit_destroyed(unit_tag)
    #
    #     # custom on_unit_destroyed logic here ...
    #
    # async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
    #     await super(Voltron, self).on_unit_took_damage(unit, amount_damage_taken)
    #
    #     # custom on_unit_took_damage logic here ...
