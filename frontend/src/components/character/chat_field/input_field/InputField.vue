<script setup >

import SendIcons from "@/components/character/chat_field/icons/SendIcons.vue";
import MicIcons from "@/components/character/chat_field/icons/MicIcons.vue";
</script>

<template>
<div class="absolute bottom-4 left-2 h-12 w-86 flex items-center">
  <input
          class="input bg-black/30 text-white text-base backdrop-blur-sm w-full rounded-2xl pr-20"
          type="text"
          placeholder="文本输入..."
  >
  <div class="absolute right-2 w-8 h-8 flex items-center justify-center cursor-pointer">
      <SendIcons/>
  </div>
    <div class="absolute right-9 w-8 h-8 flex items-center justify-center cursor-pointer">
      <MicIcons/>
  </div>
</div>
</template>

<style scoped>

</style>