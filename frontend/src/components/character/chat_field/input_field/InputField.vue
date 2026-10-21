<script setup >

import SendIcons from "@/components/character/chat_field/icons/SendIcons.vue";
import MicIcons from "@/components/character/chat_field/icons/MicIcons.vue";
import {onUnmounted, ref, useTemplateRef} from "vue";
import streamApi from "@/js/http/streamApi.js";
import Microphone from "@/components/character/chat_field/input_field/Microphone.vue";

const inputRef = useTemplateRef('input-ref')
const message = ref('')
const props = defineProps(["friendId"]);

const emit = defineEmits(["PushBackMessage", "addToLastMessage", "updateMessageState"]);

let processId = 0
const sending = ref(false)
let activeReplyId = null

let showMic = ref(false);

let mediaSource = null;
let sourceBuffer = null;
let audioPlayer = new Audio(); // 全局播放器实例
let audioQueue = [];           // 待写入 Buffer 的二进制队列
let isUpdating = false;        // Buffer 是否正在写入

const initAudioStream = () => {
    audioPlayer.pause();
    audioQueue = [];
    isUpdating = false;

    mediaSource = new MediaSource();
    audioPlayer.src = URL.createObjectURL(mediaSource);

    mediaSource.addEventListener('sourceopen', () => {
        try {
            sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');
            sourceBuffer.addEventListener('updateend', () => {
                isUpdating = false;
                processQueue();
            });
        } catch (e) {
            console.error("MSE AddSourceBuffer Error:", e);
        }
    });

    audioPlayer.play().catch(e => console.error("等待用户交互以播放音频"));
};

const processQueue = () => {
    if (isUpdating || audioQueue.length === 0 || !sourceBuffer || sourceBuffer.updating) {
        return;
    }

    isUpdating = true;
    const chunk = audioQueue.shift();
    try {
        sourceBuffer.appendBuffer(chunk);
    } catch (e) {
        console.error("SourceBuffer Append Error:", e);
        isUpdating = false;
    }
};

const stopAudio = () => {
    audioPlayer.pause();
    audioQueue = [];
    isUpdating = false;

    if (mediaSource) {
        if (mediaSource.readyState === 'open') {
            try {
                mediaSource.endOfStream();
            } catch (e) {
            }
        }
        mediaSource = null;
    }

    if (audioPlayer.src) {
        URL.revokeObjectURL(audioPlayer.src);
        audioPlayer.src = '';
    }
};

const handleAudioChunk = (base64Data) => {  // 将语音片段添加到播放器队列中
    try {
        const binaryString = atob(base64Data);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        audioQueue.push(bytes);
        processQueue();
    } catch (e) {
        console.error("Base64 Decode Error:", e);
    }
};

onUnmounted(() => {
    audioPlayer.pause();
    audioPlayer.src = '';
});


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
  if(!content || sending.value) return
  sending.value = true
  const curId =++processId
  const replyId = crypto.randomUUID()
  activeReplyId = replyId
  const updateState = (changes) => emit('updateMessageState', {id: replyId, ...changes})
  message.value = ''

  emit("PushBackMessage", {role:'user',content:content,id:crypto.randomUUID()})

  emit("PushBackMessage", {role:'ai',content:'',id:replyId,status:'thinking'})
  try{
    // Keep the existing voice behaviour without a separate checkbox.
    try { initAudioStream() }
    catch { updateState({notice: '当前浏览器暂不支持语音播放，文字回复不受影响。'}) }
    await streamApi('/api/friend/message/chat/',{
        body:{
          'friend_id':props.friendId,
          'message':content,
          'enable_tts':true
        },
        onmessage(data,isDone){

          if(curId!==processId) return
          if(isDone) {
            updateState({status: ''})
            return
          }
          if(data.status === 'optimizing') updateState({status: 'optimizing'})
          if(data.status === 'ready') updateState({status: ''})
          if(data.content){
              updateState({status: 'replying'})
              emit('addToLastMessage', data.content)
            }
          if(data.audio){
            handleAudioChunk(data.audio)
          }
          if(data.error){
            updateState({status: ''})
            emit('addToLastMessage', data.error)
          }
          if(data.warning) updateState({notice: data.warning})
        },
    })
  }catch (e){
    if(curId === processId) emit('addToLastMessage', e.message || '连接 AI 服务失败，请稍后重试。')
  }finally{
    sending.value = false
    updateState({status: ''})
    if (activeReplyId === replyId) activeReplyId = null
  }
}
function close()
{
  if (activeReplyId) emit('updateMessageState', {id: activeReplyId, status: ''})
  processId++
  showMic.value = false
  stopAudio()
}


function stop()
{
  if (activeReplyId) emit('updateMessageState', {id: activeReplyId, status: ''})
  processId++
  stopAudio()
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
    <div @click="!sending && (showMic=true)" class="absolute right-9 w-8 h-8 flex items-center justify-center cursor-pointer">
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
