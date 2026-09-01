<script setup>
import {useUserStore} from "@/stores/user";
import UserSpaceIcon from "@/components/navbar/icons/UserSpaceIcon.vue";
import UserProfileIcon from "@/components/navbar/icons/UserProfileIcon.vue";
import UserLogoutIcon from "@/components/navbar/icons/UserLogoutIcon.vue";
import api from "@/js/http/api.js";
import {useRouter} from "vue-router";

const user = useUserStore()

const router = useRouter()

function closeMenu() {//点击菜单的元素后隐藏菜单
  const element = document.activeElement
  if (element && element instanceof HTMLElement) element.blur()
}

async function logout() {

      try{
        const res =await api.post("api/user/logout/")
      const data = res.data
      if(data.result ==='success'){
        user.logout()
       await router.push({
          name:'homepage-index',
        })
      }
      else{
        error_message.value = data.result
      }
    }catch (err){
      console.log(err)
    }
}
</script>

<template>
      <div class="dropdown dropdown-end">
        <div tabindex="0" role="button" class="avatar btn btn-circle w-8 h-8 mr-6">
            <div class="w-8 rounded-full">
            <img :src="user.photo" />
           </div>
        </div>
        <ul tabindex="-1" class="dropdown-content menu bg-base-100 rounded-box z-1 w-47 p-2 shadow-lg">
          <li>
            <RouterLink @click="closeMenu()" :to="{name:'space-index',params:{user_id:user.id}}">
              <div class="avatar">
                <div class="w-10 rounded-full ">
                  <img :src="user.photo" />
                </div>
              </div>
              <span class="text-base font-bold line-clamp-1 break-all">{{user.username}}</span>
            </RouterLink>
          </li>
          <li>
             <RouterLink @click="closeMenu()" :to="{name:'space-index',params:{user_id:user.id}} "class="text-sm font-bold py-3">
               <UserSpaceIcon/>
               个人空间
            </RouterLink>
          </li>
          <li>
             <RouterLink @click="closeMenu()" :to="{name:'profile-index',params:{user_id:user.id}} "class="text-sm font-bold py-3">
               <UserProfileIcon/>
               编辑资料
            </RouterLink>
          </li>
          <li></li>
          <li>
             <a @click="logout()" class="text-sm font-bold py-3">
               <UserLogoutIcon/>
               退出
            </a>
          </li>
        </ul>
      </div>
</template>

<style scoped>

</style>