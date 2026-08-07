from endstone.plugin import Plugin
from endstone.command import Command, CommandSender
from endstone.event import event_handler, ActorSpawnEvent, ActorExplodeEvent, BlockBreakEvent, BlockPlaceEvent
from endstone.level import Location


class WitherArenaPlugin(Plugin):
    """
    Plugin that restricts Wither spawning to a designated arena, prevents
    Wither explosions from destroying blocks, restricts mob spawning in the arena,
    and protects blocks from being broken (except specific items).
    Operators can always modify blocks; repair mode disables protection for all.
    """

    # Wither Arena coordinates (Overworld)
    ARENA_MIN_X = 1587
    ARENA_MAX_X = 1705
    ARENA_MIN_Y = -64
    ARENA_MAX_Y = -40
    ARENA_MIN_Z = 1228
    ARENA_MAX_Z = 1351

    # Dimension name
    OVERWORLD = "Overworld"

    # Track mobGriefing state
    _mob_griefing_disabled = False

    # Repair mode state - when True, block protection is disabled for everyone
    _repair_mode = False

    # Allowed entities in the arena
    ALLOWED_ENTITIES = {
        "minecraft:wither",
        "gravestone_death_path:ghost",
        "gravestone_death_path:gravestone_entity",
        "npc:npc_villagers",
        "npc:npc_myentity",
        "npc:npc_monsters",
        "npc:npc_humans",
        "npc:npc_animals",
        "npc:npc_custom_expansive",
        "npc:npc_custom_slim",
        "npc:npc_custom",
        "npc:npc_custom2",
        "npc:npc_custom3",
        "npc:npc_custom4",
        "minecraft:npc"
    }

    # Blocks that can be broken in the arena
    BREAKABLE_BLOCKS = {
        "minecraft:shulker_box",
        "minecraft:white_shulker_box",
        "minecraft:orange_shulker_box",
        "minecraft:magenta_shulker_box",
        "minecraft:light_blue_shulker_box",
        "minecraft:yellow_shulker_box",
        "minecraft:lime_shulker_box",
        "minecraft:pink_shulker_box",
        "minecraft:gray_shulker_box",
        "minecraft:light_gray_shulker_box",
        "minecraft:cyan_shulker_box",
        "minecraft:purple_shulker_box",
        "minecraft:blue_shulker_box",
        "minecraft:brown_shulker_box",
        "minecraft:green_shulker_box",
        "minecraft:red_shulker_box",
        "minecraft:black_shulker_box",
        "minecraft:ender_chest",
        "gravestone_death_path:gravestone"
    }

    api_version = "0.11"

    commands = {
        "arena-repair": {
            "description": "Toggle arena repair mode (disables block protection for all players)",
            "usages": ["/arena-repair [on|off]"],
            "permissions": ["wither_arena.repair"],
        }
    }

    permissions = {
        "wither_arena.repair": {
            "description": "Allows toggling arena repair mode",
            "default": "op",
        }
    }

    def on_load(self) -> None:
        """Called when the plugin is loaded"""
        self.logger.info("WitherArenaPlugin loaded")

    def on_enable(self) -> None:
        """Called when the plugin is enabled"""
        self.logger.info("WitherArenaPlugin enabled")
        self.logger.info(f"Wither Arena boundaries: X({self.ARENA_MIN_X} to {self.ARENA_MAX_X}), "
                         f"Y({self.ARENA_MIN_Y} to {self.ARENA_MAX_Y}), "
                         f"Z({self.ARENA_MIN_Z} to {self.ARENA_MAX_Z})")

        # Register event listeners - CRITICAL for events to work!
        self.register_events(self)

        # Schedule repeating task to monitor Withers
        self.server.scheduler.run_task(
            self,
            self._monitor_withers,
            delay=60,
            period=60  # Every 60 ticks (3 seconds)
        )

    def on_disable(self) -> None:
        """Called when the plugin is disabled"""
        self.logger.info("WitherArenaPlugin disabled")

    def on_command(self, sender: CommandSender, command: Command, args: list[str]) -> bool:
        """Handle plugin commands"""
        if command.name == "arena-repair":
            # Determine the new state
            if len(args) >= 1:
                arg = args[0].lower()
                if arg == "on":
                    WitherArenaPlugin._repair_mode = True
                elif arg == "off":
                    WitherArenaPlugin._repair_mode = False
                else:
                    sender.send_message("§cUsage: /arena-repair [on|off]")
                    return True
            else:
                # Toggle if no argument provided
                WitherArenaPlugin._repair_mode = not WitherArenaPlugin._repair_mode

            # Send status message
            status = "§aON" if WitherArenaPlugin._repair_mode else "§cOFF"
            sender.send_message(f"§6Arena Repair Mode: {status}")
            
            if WitherArenaPlugin._repair_mode:
                sender.send_message("§7Block protection is now disabled for all players in the arena.")
            else:
                sender.send_message("§7Block protection is now enabled for the arena.")
            
            self.logger.info(f"Arena repair mode set to {WitherArenaPlugin._repair_mode} by {sender.name}")
            return True

        return False

    @event_handler
    def on_actor_spawn(self, event: ActorSpawnEvent) -> None:
        """Handle actor spawn events - restrict Wither spawning and prevent other mobs in arena"""
        actor = event.actor
        dimension = actor.dimension
        location = actor.location
        x, y, z = location.x, location.y, location.z

        # Check if spawn is in the arena
        in_arena = self._is_in_arena(x, y, z)

        # Handle Wither spawning
        if actor.type == "minecraft:wither":
            # Check if in Overworld
            if dimension.name != self.OVERWORLD:
                # Cancel spawn and remove the Wither if not in Overworld
                event.cancel()
                actor.remove()
                self.server.broadcast_message(
                    "§cWither spawning is only allowed in the Wither Arena."
                )
                self.logger.warning(f"Wither spawn blocked in dimension: {dimension.name}")
                return

            # Log the spawn location for debugging
            self.logger.info(f"Wither spawned at X={x:.1f}, Y={y:.1f}, Z={z:.1f}")
            self.logger.info(f"Is in arena: {in_arena}")

            if not in_arena:
                # Cancel the spawn event
                event.cancel()

                # Teleport Wither to void using keyword argument for dimension
                try:
                    actor.teleport(Location(dimension, 0, -100, 0))
                except Exception as e:
                    # If teleport fails, just remove it
                    self.logger.error(f"Failed to teleport Wither: {e}")
                    actor.remove()

                self.server.broadcast_message(
                    "§cWither spawning is restricted to the Wither Arena. "
                    "The Wither has been sent to the void."
                )
                self.logger.warning(
                    f"Wither spawned outside arena at ({x:.1f}, {y:.1f}, {z:.1f}). "
                    "Teleported to void."
                )
            else:
                self.logger.info(f"Wither spawn allowed - within arena boundaries")

        # Handle other mob spawning in the arena
        elif in_arena and dimension.name == self.OVERWORLD:
            # Check if this entity is allowed in the arena
            if actor.type not in self.ALLOWED_ENTITIES:
                # Cancel spawn of non-allowed mobs in the arena
                event.cancel()
                actor.remove()
                self.logger.debug(
                    f"Blocked {actor.type} spawn in arena at ({x:.1f}, {y:.1f}, {z:.1f})"
                )

    @event_handler
    def on_actor_explode(self, event: ActorExplodeEvent) -> None:
        """Prevent Wither explosions from destroying blocks"""
        source = event.actor

        # Check if explosion is caused by a Wither
        if source and source.type == "minecraft:wither":
            # Cancel the explosion to prevent block destruction
            event.cancel()
            self.logger.debug("Cancelled Wither explosion to prevent block destruction")

    @event_handler
    def on_block_break(self, event: BlockBreakEvent) -> None:
        """Prevent players from breaking blocks in the arena except allowed blocks"""
        block = event.block
        player = event.player

        # Get block location
        location = block.location
        x, y, z = location.x, location.y, location.z

        # Check if block is in the arena
        if not self._is_in_arena(x, y, z):
            return  # Not in arena, allow normal breaking

        # Allow operators to always break blocks in the arena
        if player.is_op:
            return

        # Allow everyone to break blocks if repair mode is enabled
        if WitherArenaPlugin._repair_mode:
            return

        # Check if block is in the allowed list
        block_type = block.type
        if block_type not in self.BREAKABLE_BLOCKS:
            # Cancel the block break event
            event.cancel()
            player.send_message("§cYou cannot break blocks in the Wither Arena!")
            self.logger.debug(
                f"Blocked {player.name} from breaking {block_type} at ({x:.1f}, {y:.1f}, {z:.1f})"
            )

    @event_handler
    def on_block_place(self, event: BlockPlaceEvent) -> None:
        """Prevent players from placing blocks in the arena"""
        player = event.player
        block = event.block

        # Get block location
        location = block.location
        x, y, z = location.x, location.y, location.z

        # Check if block is in the arena
        if not self._is_in_arena(x, y, z):
            return  # Not in arena, allow normal placement

        # Allow operators to always place blocks in the arena
        if player.is_op:
            return

        # Allow everyone to place blocks if repair mode is enabled
        if WitherArenaPlugin._repair_mode:
            return

        # Cancel the block place event for non-operators
        event.cancel()
        player.send_message("§cYou cannot place blocks in the Wither Arena!")
        self.logger.debug(
            f"Blocked {player.name} from placing block at ({x:.1f}, {y:.1f}, {z:.1f})"
        )

    def _monitor_withers(self) -> None:
        """
        Periodic task to monitor Withers and apply restrictions.
        Runs every 60 ticks (3 seconds).
        """
        try:
            # Get all actors from the level
            all_actors = self.server.level.actors

            # Count Withers in the arena
            withers_in_arena = 0

            # Filter for Withers in the Overworld
            for actor in all_actors:
                if actor.type != "minecraft:wither":
                    continue

                if not actor.is_valid:
                    continue

                # Check if in Overworld
                if actor.dimension.name != self.OVERWORLD:
                    continue

                location = actor.location
                x, y, z = location.x, location.y, location.z

                # Check if Wither is in the arena
                if self._is_in_arena(x, y, z):
                    withers_in_arena += 1

                    # Ensure Wither stays above minimum Y level
                    min_y = self.ARENA_MIN_Y - 10
                    if y < min_y:
                        try:
                            overworld = self.server.level.get_dimension(self.OVERWORLD)
                            new_location = Location(overworld, x, min_y, z)
                            actor.teleport(new_location)
                            self.logger.info(
                                f"Teleported Wither from Y={y:.1f} to Y={min_y}"
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to teleport Wither: {e}")

            # Manage mobGriefing game rule based on arena Wither count
            if withers_in_arena > 0 and not self._mob_griefing_disabled:
                # Disable mob griefing to prevent Wither from destroying blocks
                self.server.dispatch_command(self.server.command_sender, "gamerule mobGriefing false")
                self._mob_griefing_disabled = True
                self.logger.info(f"Disabled mobGriefing - {withers_in_arena} Wither(s) in arena")
            elif withers_in_arena == 0 and self._mob_griefing_disabled:
                # Re-enable mob griefing when no Withers in arena
                self.server.dispatch_command(self.server.command_sender, "gamerule mobGriefing true")
                self._mob_griefing_disabled = False
                self.logger.info("Re-enabled mobGriefing - no Withers in arena")

        except Exception as e:
            self.logger.error(f"Error in _monitor_withers: {e}")

    def _is_in_arena(self, x: float, y: float, z: float) -> bool:
        """Check if coordinates are within the Wither Arena"""
        return (self.ARENA_MIN_X <= x <= self.ARENA_MAX_X and
                self.ARENA_MIN_Y <= y <= self.ARENA_MAX_Y and
                self.ARENA_MIN_Z <= z <= self.ARENA_MAX_Z)
