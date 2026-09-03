<script setup>


import {nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef} from "vue";
import api from "@/js/http/api.js";
import Character from "@/components/character/character.vue";

const characters = ref([])
const isLoading = ref(false);
const hasCharacters = ref(true);
const sentinelRef = useTemplateRef('sentienl-ref')

function checkSentinelVisible() {  // 判断哨兵是否能被看到
  if (!sentinelRef.value) return false

  const rect = sentinelRef.value.getBoundingClientRect()
  return rect.top < window.innerHeight && rect.bottom > 0
}
async function loadCharacters() {
  if (isLoading.value||!hasCharacters.value) return
  isLoading.value = true

  let newCharacters = []

  try{
    const res = await api.get('/api/homePage/index/',{
      params: {
        'items_count':characters.value.length,
      }
    })
    const data = res.data
    if(data.result==='success'){
      newCharacters = data.characters
    }
  }catch(error){
    console.log(error)
  }finally {
    isLoading.value = false
    if(newCharacters.length===0){
      hasCharacters.value = false

    }else {
      characters.value.push(...newCharacters)
      await nextTick()//等待渲染元素
      if(checkSentinelVisible)
      {
        await loadCharacters()
      }
    }
  }
}
let observer = null
onMounted(async () => {
  await loadCharacters()
  observer = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          loadMore()
        }
      })
    },
    {root: null, rootMargin: '2px', threshold: 0}
  )

  //监听哨兵元素， 每次哨兵被看到时，都会触发一次
  observer.observe(sentinelRef.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>

<template>
<div class="flex items-center flex-col mb-12">

  <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-9 mt-12 justify-items-center w-full px-9">
      <character
          v-for="character in characters"
          :key="character.id"
          :character="character"
      />
  </div>
  <div ref="sentienl-ref" class="h-2 mt-8 w-100"></div>
  <div v-if="isLoading" class="text-gray-500 mt-4">正在加载中...</div>
  <div v-else-if="!hasCharacters" class="text-sm text-gray-500 mt-4">没有更多角色了</div>
</div>
</template>

<style scoped>

</style>