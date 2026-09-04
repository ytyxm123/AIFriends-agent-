<script setup>

import {nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef} from "vue";
import api from "@/js/http/api.js";
import Character from "@/components/character/character.vue";
const friend = ref([])
const isLoading = ref(false)
const hasFriends = ref(true);

const sentinelRef = useTemplateRef('sentinel-ref')

function checkSentinelVisible() {  // 判断哨兵是否能被看到
  if (!sentinelRef.value) return false

  const rect = sentinelRef.value.getBoundingClientRect()
  return rect.top < window.innerHeight && rect.bottom > 0
}

async function loadFriends() {
  if(isLoading.value||!hasFriends.value){
    return
  }
  let  newFriends=[]
  isLoading.value = true;
  try{
    const res = await api.get('/api/get_list/friends/',
        {
          params: {
            items_count: friend.value.length,
          }
        })
    const data = res.data
    if(data.result==='success'){
      newFriends = data.friends
    }
  }catch(e){
  }finally {
    isLoading.value = false
    if(newFriends.length===0){
      hasFriends.value = false
    }else{
      friend.value.push(...newFriends)
      await nextTick()
      if(checkSentinelVisible()){
        await loadFriends()
      }
    }
  }
}
let observer = null
onMounted(async () => {
  await loadFriends()  // 加载新元素

  observer = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          loadFriends()
        }
      })
    },
    {root: null, rootMargin: '2px', threshold: 0}
  )

  //监听哨兵元素， 每次哨兵被看到时，都会触发一次
  observer.observe(sentinelRef.value)
})

 async function removeFriend (friendId) {
  friend.value = friend.value.filter(f => f.id!==friendId)
}

onBeforeUnmount(() => {
  observer?.disconnect()  // 解绑监听器
})

</script>

<template>
<div class="flex flex-col items-center mb-12">
  <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-9 mt-12 justify-items-center w-full px-9">
      <character
          v-for="friend in friend"
          :key="friend.id"
          :character="friend.character"
          :canRemoveFriend="true"
          :friendId="friend.id"
          @remove="removeFriend"
      />
  </div>

  <div ref="sentinel-ref" class="h-2 mt-8"></div>
  <div v-if="isLoading" class="text-sm text-gray-500 mt-4">加载中...</div>
  <div v-else-if="!hasFriends" class="text-sm text-gray-500mt-4">没有更多聊天了</div>
</div>
</template>

<style scoped>

</style>