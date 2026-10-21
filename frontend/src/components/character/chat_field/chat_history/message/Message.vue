<script setup>

import {computed} from "vue";
import {useUserStore} from "@/stores/user.js";

const props = defineProps(['message','character'])

const user = useUserStore()
const progressText = computed(() => ({
  thinking: '正在思考…',
  replying: '正在回复…',
  optimizing: '正在优化对话…',
}[props.message.status] || ''))

</script>

<template>
<div v-if="message.content || message.status || message.notice">
    <div v-if="message.role==='ai'" class="chat chat-start">
      <div class="chat-image avatar">
        <div class="w-10 rounded-full">
          <img
            alt=""
            :src="character.photo"
          />
        </div>
      </div>
      <div>
        <!-- Request progress, not fabricated model reasoning or answer text. -->
        <div v-if="progressText" class="mb-1 flex items-center gap-2 rounded-lg bg-base-100/90 px-3 py-2 text-xs text-base-content/70" role="status" aria-live="polite">
          <span class="loading loading-dots loading-xs" aria-hidden="true"></span>
          <span>{{ progressText }}</span>
        </div>
        <div v-if="message.content" class="chat-bubble whitespace-pre-wrap break-all">{{message.content}}</div>
        <p v-if="message.notice" class="mt-1 rounded-lg bg-base-100/90 px-3 py-2 text-xs text-base-content/70" role="status">{{ message.notice }}</p>
      </div>
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
