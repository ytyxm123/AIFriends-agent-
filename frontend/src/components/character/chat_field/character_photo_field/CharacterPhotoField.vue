<script setup>
defineProps(['character'])

</script>

<template>
<div class="absolute left-2 right-56 top-6 bg-black/50 flex items-center gap-2 px-2 rounded-full">

  <div class="avatar">
      <div class="w-8 rounded-full">
        <img :src="character.photo" alt="" />
      </div>
  </div>

  <div class="text-white line-clamp-1 break-all">
    {{character.name}}
  </div>
</div>
</template>

<style scoped>

</style>