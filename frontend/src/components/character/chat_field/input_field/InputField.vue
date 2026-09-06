<script setup >

import SendIcons from "@/components/character/chat_field/icons/SendIcons.vue";
import MicIcons from "@/components/character/chat_field/icons/MicIcons.vue";
import {ref, useTemplateRef} from "vue";
import streamApi from "@/js/http/streamApi.js";

const inputRef = useTemplateRef('input-ref')
const message = ref('')
const props = defineProps(["friendId"]);

const emit = defineEmits(["PushBackMessage", "addToLastMessage"]);

let isProcessing = false
function focus()
{
  inputRef.value.focus()
}

async function sendMessage()
{




  const content = message.value.trim()
  if(!content) return
    if(isProcessing){
    return
  }
  isProcessing = true
  message.value = ''

  emit("PushBackMessage", {role:'user',content:content,id:crypto.randomUUID()})

  emit("PushBackMessage", {role:'ai',content:'',id:crypto.randomUUID()})
  try{
    const res = await streamApi('/api/friend/message/chat/',{
        body:{
          'friend_id':props.friendId,
          'message':content
        },
        onmessage(data,isDone){
            if(isDone){
              isProcessing = false
            }else if(data.content){
              emit('addToLastMessage', data.content)
            }
        },
        onerror(err){
          isProcessing = false
        }
    })
  }catch (e){
    console.error(e)
    isProcessing = false
  }
}

defineExpose({
      focus,
})
</script>

<template>
<form @submit.prevent="sendMessage" class="absolute bottom-4 left-2 h-12 w-86 flex items-center">
  <input
          ref="input-ref"
          v-model="message"
          class="input bg-black/30 text-white text-base backdrop-blur-sm w-full rounded-2xl pr-20"
          type="text"
          placeholder="文本输入..."
  >
  <div @click="sendMessage" class="absolute right-2 w-8 h-8 flex items-center justify-center cursor-pointer">
      <SendIcons/>
  </div>
    <div class="absolute right-9 w-8 h-8 flex items-center justify-center cursor-pointer">
      <MicIcons/>
  </div>
</form>
</template>

<style scoped>

</style>