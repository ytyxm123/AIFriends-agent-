<script setup>
import {ref} from "vue";
import {useUserStore} from "@/stores/user.js";
import UpdateIcons from "@/components/navbar/icons/UpdateIcons.vue";
import RemoveIcons from "@/components/navbar/icons/RemoveIcons.vue";
import api from "@/js/http/api.js";

const props = defineProps(['character','canEdit'])

const isHover = ref(false);
const user = useUserStore()
const emit = defineEmits(["remove"]);

async function removeCharacter() {

  try{
    const res = await api.post('/api/remove/character/',{
      'character_id':props.character.id
    })
    const data = res.data;
    if(data.result === 'success'){
        emit("remove", props.character.id);
    }
  }catch(error){
  }
}
</script>

<template>
<div>
  <div class="avatar cursor-pointer" @mouseover="isHover = true" @mouseout="isHover = false" >
      <div class="w-60 h-100 rounded-2xl relative"  >
          <img :src="character.background_image"  class="transition-transform duration-300" alt="" :class="{'scale-120':isHover}">
          <div class="absolute left-0 top-50 w-60 h-50 bg-linear-to-t from-black/40 to-transparent"></div>

            <div v-if="canEdit && character.author.user_id === user.id" class="absolute right-0 top-50">
              <RouterLink :to="{name:'character-update-index',params:{character_id:character.id}}" class="btn btn-circle btn-ghost bg-transparent">
              <UpdateIcons/>
            </RouterLink>
            <button class="btn btn-circle btn-ghost bg-transparent">
            <RemoveIcons @click="removeCharacter"/>
            </button>
            </div>

            <div class="absolute left-4 top-54 avatar">
              <div  class="w-16 rounded-full ring-3 ring-white">
                <img  :src="character.photo" alt=""/>
              </div>
            </div>
            <div class="absolute left-24 right-4 top-58 text-white font-bold line-clamp-1 break-all">{{character.name}}</div>
            <div class="absolute left-4 top-72 right-4 text-white font-bold line-clamp-4 break-all">{{character.profile}}</div>
      </div>
  </div>
       <RouterLink :to="{name:'space-index',params:{user_id:character.author.user_id}}" class="flex items-center mt-4 gap-2 w-60" >
       <div class="avatar">
         <div class="w-7 rounded-full">
           <img  :src="character.author.photo" alt="">
         </div>
       </div>
         <div class="text-sm line-clamp-1 break-all">{{ character.author.username }}</div>
     </RouterLink>
</div>
</template>

<style scoped>

</style>