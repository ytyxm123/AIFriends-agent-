<script setup>
const props = defineProps(['voices','curVoiceId'])
import {ref, watch} from "vue";


const myVoice = ref(props.curVoiceId || '')
watch(() => props.curVoiceId, (newValue) => {
  myVoice.value = newValue || ''
})

defineExpose({
  myVoice,
})
</script>

<template>
<fieldset class="fieldset">
  <label class="label text-base">音色</label>
  <select class="select" v-model="myVoice">
      <option value="">仅文字，不使用音色</option>
      <option
          v-for="voice in voices"
          :id="voice.id"
          :value="voice.id"
      >{{voice.name}}</option>
</select>
</fieldset>
</template>

<style scoped>

</style>
