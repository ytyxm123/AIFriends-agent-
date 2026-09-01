<script setup>

import {ref, watch} from "vue";

const props = defineProps(['profile'])
const myProfile = ref(props.profile)
watch(() => props.profile, (newValue) => {
  myProfile.value = newValue
})

defineExpose({
  myProfile,
})
</script>

<template>
<fieldset class="fieldset">
  <label class="label text-base">角色介绍</label>
  <textarea v-model="myProfile" class="textarea w-108" rows="6"></textarea>
</fieldset>
</template>

<style scoped>

</style>