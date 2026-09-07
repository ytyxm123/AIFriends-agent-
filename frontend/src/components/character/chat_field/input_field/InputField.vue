<script setup >

import SendIcons from "@/components/character/chat_field/icons/SendIcons.vue";
import MicIcons from "@/components/character/chat_field/icons/MicIcons.vue";
import {ref, useTemplateRef} from "vue";
import streamApi from "@/js/http/streamApi.js";
import Microphone from "@/components/character/chat_field/input_field/Microphone.vue";

const inputRef = useTemplateRef('input-ref')
const message = ref('')
const props = defineProps(["friendId"]);

const emit = defineEmits(["PushBackMessage", "addToLastMessage"]);

let processId = 0

let showMic = ref(false);
function focus()
{
  inputRef.value.focus()
}

async function sendMessage(event,audio_msg)
{
  let content
  if(audio_msg){
    content = audio_msg.trim()
  }else{
    content = message.value.trim()
  }
  if(!content) return
  const curId =++processId
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

          if(curId!==processId) return
          if(data.content){
              emit('addToLastMessage', data.content)
            }
        },
        onerror(err){
        }
    })
  }catch (e){
  }
}
function close()
{
  processId++
  showMic.value = false
}


function stop()
{
  processId++
}
defineExpose({
      focus,
      close
})
</script>

<template>
<form v-if="!showMic" @submit.prevent="sendMessage" class="absolute bottom-4 left-2 h-12 w-86 flex items-center">
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
    <div @click="showMic=true" class="absolute right-9 w-8 h-8 flex items-center justify-center cursor-pointer">
      <MicIcons/>
  </div>
</form>
  <Microphone v-else
              @close="showMic = false"
              @send="sendMessage"
              @stop="stop"
  />
</template>

<style scoped>

</style>