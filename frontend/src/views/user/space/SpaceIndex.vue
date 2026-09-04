<script setup>

import UserInfoField from "@/views/user/space/components/UserInfoField.vue";
import {nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch} from "vue";
import api from "@/js/http/api.js";
import {useRoute} from "vue-router";
import Character from "@/components/character/character.vue";

const userProfile = ref(null);
const characters = ref([])
const isLoading = ref(false)
const hasCharacter = ref(true)
const sentinelRef = useTemplateRef('sentinel-ref')
const route = useRoute();

function reset()
{
  userProfile.value = null
  characters.value = []
  isLoading.value = false
  hasCharacter.value = true
  loadCharacter()
}

watch(()=>route.params.user_id,()=>{
      reset()
})

function checkSentinelVisible() {  // 判断哨兵是否能被看到
  if (!sentinelRef.value) return false

  const rect = sentinelRef.value.getBoundingClientRect()
  return rect.top < window.innerHeight && rect.bottom > 0
}

async function loadCharacter() {
  if(isLoading.value||!hasCharacter.value) return
  isLoading.value = true

  let newCharacters = []
  try{
    const res = await api.get('/api/get_list/character/',{
      params:{
          items_count: characters.value.length,
          user_id:route.params.user_id
      }
    })

    const data = res.data
    if(data.result === 'success'){
      userProfile.value = data.user_profile
      newCharacters = data.characters
    }
  }catch(error) {
    console.log(error)
  }finally {
    isLoading.value = false
    if(newCharacters.length===0)
    {
      hasCharacter.value = false
    }else{
      characters.value.push(...newCharacters)
      await nextTick()
      if(checkSentinelVisible()){
        await loadCharacter()
      }
    }
  }
}


let observer = null

onMounted(async () => {
  await loadCharacter()  // 加载新元素

  observer = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          loadCharacter()
        }
      })
    },
    {root: null, rootMargin: '2px', threshold: 0}
  )

  //监听哨兵元素， 每次哨兵被看到时，都会触发一次
  observer.observe(sentinelRef.value)
})
function removeCharacter(characterId) {
  characters.value = characters.value.filter(c=>c.id!==characterId)
}


onBeforeUnmount(() => {
  observer?.disconnect()  // 解绑监听器
})

</script>

<template>
<div class="flex flex-col  items-center mb-12">
  <UserInfoField :userProfile="userProfile"/>
  <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-9 mt-12 justify-items-center w-full px-9">
      <character
          v-for="character in characters"
          :key="character.id"
          :character="character"
          :canEdit="true"
          @remove="removeCharacter"
      />
  </div>
  <div ref="sentinel-ref" class="h-2 mt-8 w-100"></div>
  <div v-if="isLoading" class="text-gray-500 mt-4">加载中...</div>
  <div v-else-if="!hasCharacter" class="text-gray-500 mt-4">没有更多角色了</div>
</div>
</template>

<style scoped>

</style>