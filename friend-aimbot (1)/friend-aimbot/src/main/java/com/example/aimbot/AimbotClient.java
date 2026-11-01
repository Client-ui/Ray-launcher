package com.example.aimbot;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.text.Text;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;
import org.lwjgl.glfw.GLFW;

public class AimbotClient implements ClientModInitializer {
    private static boolean enabled = false;
    private static KeyBinding toggleKey;

    private static final double RANGE = 6.0;
    private static final float SMOOTHING = 0.3f;

    @Override
    public void onInitializeClient() {
        toggleKey = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.aimbot.toggle", InputUtil.Type.KEYSYM,
                GLFW.GLFW_KEY_R, "category.aimbot"));

        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            while (toggleKey.wasPressed()) {
                enabled = !enabled;
                if (client.player != null) {
                    client.player.sendMessage(
                        Text.literal("Aimbot: " + (enabled ? "ON" : "OFF")), true);
                }
            }
            if (!enabled || client.player == null || client.world == null) return;

            ClientPlayerEntity me = client.player;
            PlayerEntity target = null;
            double best = RANGE * RANGE;

            for (PlayerEntity p : client.world.getPlayers()) {
                if (p == me || !p.isAlive()) continue;
                double d = me.squaredDistanceTo(p);
                if (d < best) { best = d; target = p; }
            }
            if (target == null) return;

            Vec3d diff = target.getEyePos().subtract(me.getEyePos());
            double horizontal = Math.sqrt(diff.x * diff.x + diff.z * diff.z);
            float yaw = (float) (Math.toDegrees(Math.atan2(diff.z, diff.x)) - 90.0);
            float pitch = (float) -Math.toDegrees(Math.atan2(diff.y, horizontal));

            me.setYaw(MathHelper.lerpAngleDegrees(SMOOTHING, me.getYaw(), yaw));
            me.setPitch(MathHelper.lerp(SMOOTHING, me.getPitch(), pitch));
        });
    }
}
