<script setup>

import {useUserStore} from "@/stores/user.js";

defineProps(['message','character'])

const user = useUserStore()
</script>

<template>
<div v-if="message.content">
    <div v-if="message.role==='ai'" class="chat chat-start">
      <div class="chat-image avatar">
        <div class="w-10 rounded-full">
          <img
            alt=""
            :src="character.photo"
          />
        </div>
      </div>
      <div class="chat-bubble whitespace-pre-wrap break-all">{{message.content}}</div>
    </div>
    <div v-else>
      <div class="chat chat-end">
        <div class="chat-image avatar">
        <div class="w-10 rounded-full">
          <img
            alt=""
            :src="user.photo"
          />
        </div>
      </div>
        <div class="chat-bubble chat-bubble-info whitespace-pre-wrap break-all">{{message.content}}</div>
      </div>
    </div>
</div>
</template>

<style scoped>

</style>