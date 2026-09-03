import { createRouter, createWebHistory } from 'vue-router'

// @ts-ignore
import HomepageIndex from "@/views/Homepage/HomepageIndex.vue";
import FriendIndex from "@/views/friends/FriendIndex.vue";
// @ts-ignore
import CreateIndex from "@/views/create/CreateIndex.vue";
// @ts-ignore
import RegisterIndex from "@/views/user/account/RegisterIndex.vue";
import NotFoundIndex from "@/views/error/NotFoundIndex.vue";
// @ts-ignore
import ProfileIndex from "@/views/user/profile/ProfileIndex.vue";
// @ts-ignore
import SpaceIndex from "@/views/user/space/SpaceIndex.vue";
// @ts-ignore
import LoginIndex from "@/views/user/account/LoginIndex.vue";

// @ts-ignore
import {useUserStore} from "@/stores/user";
// @ts-ignore
import UpdateCharacter from "@/views/create/character/UpdateCharacter.vue";


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [

    {
      path:'/',
      component:HomepageIndex,
      name:'homepage-index',
      meta:{
        needLogin:false,
      }
    },
    {
      path:'/friend/',
      component:FriendIndex,
      name:'Friend-index',
      meta:{
        needLogin:true,
      }
    },
    {
      path:'/create/',
      component:CreateIndex,
      name:'create-index',
      meta:{
        needLogin:true,
      }
    },
    {
      path:'/create/character/update/:character_id',
      component:UpdateCharacter,
      name:'character-update-index',
      meta:{
        needLogin:true,
      }
    },
    {
      path:'/login/',
      component:LoginIndex,
      name:'login-index',
      meta:{
        needLogin:false,
      }
    },
    {
      path:'/register/',
      component:RegisterIndex,
      name:'register-index',
      meta:{
        needLogin:false,
      }
    },
    {
      path:'/NotFound/',
      component:NotFoundIndex,
      name:'not-found',
      meta:{
        needLogin:false,
      }
    },
    {
      path:'/profile/',
      component:ProfileIndex,
      name:'profile-index',
      meta:{
        needLogin:true,
      }
    },
    {
      path:'/space/:user_id/',
      component:SpaceIndex,
      name:'space-index',
      meta:{
        needLogin:false,
      }
    },
    {
      path:'/:pathMatch(.*)*',
      component:NotFoundIndex,
      name:'not-found',
      meta:{
        needLogin:false,
      }
    }
  ],
})
router.beforeEach((to,from)=>{
    const user = useUserStore()
  if(to.meta.needLogin && !user.isLogin() && user.HasPullInfo){
    return{
      name:'login-index',
    }
  }
})
export default router
