<script setup>
import {ref, watch} from "vue";

const props = defineProps(['username'])

const myUsername = ref(props.username)
watch(() => props.username, (newValue) => {
  myUsername.value = newValue
})

defineExpose({
  myUsername
})
</script>

<template>

  <fieldset class="fieldset">
    <label class="label text-base">用户名</label>
    <input type="text" class="input w-108" v-model="myUsername">
  </fieldset>
</template>

<style scoped>

</style>